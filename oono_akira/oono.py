import asyncio
import ssl
import json
import time
import websockets
from collections import deque
from aiohttp import web
from aiohttp import ClientSession
from aiohttp.web_request import Request
from oono_akira.db import OonoDatabase
from oono_akira.slack import SlackAPI, SlackContext
from oono_akira.modules import ModulesManager
from oono_akira.log import log


class OonoAkira:

    PAYLOAD_TRACKER_SIZE = 1024

    def __init__(self, config: dict):

        slack = config["slack"]
        self._slack_oauth = {
            "client_id": slack["client_id"],
            "client_secret": slack["client_secret"],
            "redirect_uri": slack["redirect_uri"],
        }
        self._slack_app_token = slack["token"]

        self._db = OonoDatabase(config["db"]["path"])

        server = config["server"]
        if "ssl" in server:
            self._ssl_context = ssl.SSLContext()
            self._ssl_context.load_cert_chain(server["ssl"]["cert"], server["ssl"]["key"])
        else:
            self._ssl_context = None
        self._web_app = web.Application()
        self._web_app.add_routes([web.get("/oauth", self._oauth_handler)])
        self._web_port = server.get("port", 25472)

        self._payload_queue = deque()
        self._payload_set = set()

    async def __aenter__(self):

        # database
        self._db.initialize()

        # workspace modules
        self._modules = ModulesManager()

        # client
        self._api_client = ClientSession()
        self._ws_client = ClientSession(headers={"Authorization": f"Bearer {self._slack_app_token}"})

        # server
        self._web_runner = web.AppRunner(self._web_app)
        await self._web_runner.setup()
        self._web_site = web.TCPSite(self._web_runner, port=self._web_port, ssl_context=self._ssl_context)
        await self._web_site.start()

        return self

    async def __aexit__(self, *err):
        await self._api_client.close()
        await self._ws_client.close()

    async def _oauth_handler(self, request: Request):
        code = request.rel_url.query["code"]
        resp = await SlackAPI(self._api_client).oauth.v2.access(code=code, **self._slack_oauth)
        if not resp["ok"]:
            return web.Response(text=resp["error"])
        self._db.add_workspace(
            resp["team"]["id"], resp["team"]["name"],
            resp["bot_user_id"], resp["authed_user"]["id"],
            resp["access_token"])
        self._db.record_payload("oauth_access_token", resp)
        return web.Response(text="Done" if resp["ok"] else "Error")

    async def run(self):
        while True:
            try:
                log("Trying to establish connection")
                conn_resp = await self._ws_client.post("https://slack.com/api/apps.connections.open")
                if not conn_resp.ok:
                    log("Failed to request connections.open, retrying...")
                    time.sleep(5)
                    continue

                conn_url = await conn_resp.json()
                if not conn_url["ok"]:
                    log(f"connections.open() returned error: {conn_url['error']}, retrying...")
                    time.sleep(5)
                    continue

                async with websockets.connect(conn_url["url"], close_timeout=0) as conn:
                    async for payload_str in conn:

                        payload = json.loads(payload_str)
                        self._db.record_payload(f"websocket_{payload['type']}", payload_str)

                        if payload["type"] == "events_api":
                            if not self._track_payload(payload["payload"]["event_id"]):
                                log(f"Duplicate payload: {payload['payload']['event_id']}")
                                continue
                            ack = await self._process_event(payload["payload"])
                            asyncio.create_task(self._ack_event(conn, payload, ack))
                        elif payload["type"] == "hello":
                            log(f"WebSocket connection established, appid = {payload['connection_info']['app_id']}")
                        elif payload["type"] == "disconnect":
                            log(f"Received disconnect request, reason: {payload['reason']}")
                            await conn.close()
                            break

                log(f"Disconnected.")

            except Exception:

                import traceback
                traceback.print_exc()

    def _track_payload(self, track_id) -> bool:
        if track_id in self._payload_set:
            return False
        self._payload_queue.append(track_id)
        self._payload_set.add(track_id)
        if len(self._payload_queue) > self.PAYLOAD_TRACKER_SIZE:
            item = self._payload_queue.popleft()
            self._payload_set.remove(item)
        return True

    async def _process_event(self, event):
        ws_info = self._db.get_workspace_info(event["team_id"])
        if event.get("event", {}).get("user") == ws_info["bot_id"]:
            return
        context = SlackContext({
            "workspace": {
                "name": ws_info["workspace_name"],
                "bot": ws_info["bot_id"],
                "admin": ws_info["admin_id"],
            },
            "event": event["event"],
            "database": self._db,
        })
        ev_type = event["event"]["type"]
        for module_name in self._modules.get_capable_modules(ev_type):
            module = self._modules.get_module(module_name)
            check_func = getattr(module["class"], f"check_{ev_type}")
            if check_func(context):
                break
        else:
            return
        api = SlackAPI(self._api_client, {"token": ws_info["workspace_token"]})
        return await module["class"](api, context).process()

    async def _ack_event(self, conn, payload, ack):
        ack_str = json.dumps({
            "envelope_id": payload["envelope_id"],
            "payload": ack
        })
        await conn.send(ack_str)
