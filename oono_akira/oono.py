import asyncio
import ssl
import json
import time
import traceback
from contextlib import AsyncExitStack
from collections import deque
from typing import Deque, Set, Tuple, Any

import websockets.client
from aiohttp import web
from aiohttp import ClientSession
from aiohttp.web_request import Request

from oono_akira.config import Configuration
from oono_akira.db import OonoDatabase
from oono_akira.slack import SlackAPI, SlackContext
from oono_akira.modules import ModulesManager
from oono_akira.log import log


class OonoAkira:

    PAYLOAD_TRACKER_SIZE = 1024

    def __init__(self, config: Configuration):

        slack = config["slack"]
        self._slack_oauth = {
            "client_id": slack["client_id"],
            "client_secret": slack["client_secret"],
            "redirect_uri": slack["redirect_uri"],
        }
        self._slack_app_token = slack["token"]
        self._slack_permissions = slack["permissions"]

        self._db = OonoDatabase(config["database"])

        server = config["server"]
        if "ssl" in server:
            self._ssl_context = ssl.SSLContext()
            self._ssl_context.load_cert_chain(
                server["ssl"]["cert"], server["ssl"]["key"]
            )
        else:
            self._ssl_context = None
        self._web_app = web.Application()
        self._web_app.add_routes([web.get("/oauth", self._oauth_handler)])
        self._web_app.add_routes([web.get("/install", self._install_handler)])
        self._web_port = server.get("port", 25472)

        self._payload_queue: Deque[str] = deque()
        self._payload_set: Set[str] = set()

    async def __aenter__(self):

        # database
        self._db.initialize()

        self._ack_queue: asyncio.Queue[Tuple[str, Any]] = asyncio.Queue()

        async with AsyncExitStack() as stack:
            self._api_client = await stack.enter_async_context(ClientSession())
            self._ws_client = await stack.enter_async_context(
                ClientSession(
                    headers={"Authorization": f"Bearer {self._slack_app_token}"}
                )
            )
            self._modules = await stack.enter_async_context(ModulesManager())
            self._stack = stack.pop_all()

        # server
        self._web_runner = web.AppRunner(self._web_app)
        await self._web_runner.setup()
        self._web_site = web.TCPSite(
            self._web_runner, port=self._web_port, ssl_context=self._ssl_context
        )
        await self._web_site.start()

        return self

    async def __aexit__(self, *_):
        await self._web_site.stop()
        await self._web_runner.cleanup()
        await self._stack.aclose()

    async def _oauth_handler(self, request: Request):
        code = request.rel_url.query["code"]
        resp = await SlackAPI(self._api_client).oauth.v2.access(
            code=code, **self._slack_oauth
        )
        if not resp["ok"]:
            return web.Response(text=resp["error"])
        self._db.add_workspace(
            resp["team"]["id"],
            resp["team"]["name"],
            resp["bot_user_id"],
            resp["authed_user"]["id"],
            resp["access_token"],
        )
        self._db.record_payload("oauth_access_token", resp)
        return web.Response(text="Done" if resp["ok"] else "Error")

    async def _install_handler(self, request: Request):
        auth_uri = "https://slack.com/oauth/v2/authorize?client_id={}&scope={}&redirect_uri={}".format(
            self._slack_oauth["client_id"],
            ",".join(self._slack_permissions),
            self._slack_oauth["redirect_uri"],
        )
        raise web.HTTPFound(auth_uri)

    async def run(self):
        while True:
            try:
                log("Trying to establish connection")
                conn_resp = await self._ws_client.post(
                    "https://slack.com/api/apps.connections.open"
                )
                if not conn_resp.ok:
                    log("Failed to request connections.open, retrying...")
                    time.sleep(5)
                    continue

                conn_url = await conn_resp.json()
                if not conn_url["ok"]:
                    log(
                        f"connections.open() returned error: {conn_url['error']}, retrying..."
                    )
                    time.sleep(5)
                    continue

                async with websockets.client.connect(
                    conn_url["url"], close_timeout=0
                ) as conn:
                    recv = asyncio.create_task(conn.recv())
                    ack = asyncio.create_task(self._ack_queue.get())
                    pending = {recv, ack}
                    while True:
                        done, pending = await asyncio.wait(
                            pending, return_when=asyncio.FIRST_COMPLETED
                        )
                        if recv in done:
                            # Start a new recv task
                            recv_result = await recv
                            recv = asyncio.create_task(conn.recv())
                            pending.add(recv)
                            # Process recv
                            payload = json.loads(recv_result)
                            self._db.record_payload(
                                f"websocket_{payload['type']}", recv_result
                            )
                            if payload["type"] == "events_api":
                                if not self._track_payload(
                                    payload["payload"]["event_id"]
                                ):
                                    log(
                                        f"Duplicate payload: {payload['payload']['event_id']}"
                                    )
                                else:
                                    await self._process_event(payload)
                            elif payload["type"] == "hello":
                                log(
                                    f"WebSocket connection established, appid = {payload['connection_info']['app_id']}"
                                )
                            elif payload["type"] == "disconnect":
                                log(
                                    f"Received disconnect request, reason: {payload['reason']}"
                                )
                                await conn.close()
                                break
                        if ack in done:
                            # Start a new ack task
                            ack_result = await ack
                            ack = asyncio.create_task(self._ack_queue.get())
                            pending.add(ack)
                            # Process ack
                            envelope_id, ack_payload = ack_result
                            ack_str = json.dumps(
                                {"envelope_id": envelope_id, "payload": ack_payload}
                            )
                            asyncio.create_task(conn.send(ack_str))
                log(f"Disconnected.")

            except Exception:
                traceback.print_exc()

    def _track_payload(self, track_id: str) -> bool:
        if track_id in self._payload_set:
            return False
        self._payload_queue.append(track_id)
        self._payload_set.add(track_id)
        if len(self._payload_queue) > self.PAYLOAD_TRACKER_SIZE:
            item = self._payload_queue.popleft()
            self._payload_set.remove(item)
        return True

    async def _process_event(self, payload: Any) -> bool:
        event = payload["payload"]
        ws_info = self._db.get_workspace_info(event["team_id"])
        # Ignore if event payload is me
        if event.get("event", {}).get("user") == ws_info["bot_id"]:
            await self._ack_queue.put((payload["envelope_id"], None))
            return False
        context = SlackContext(
            {
                "workspace": {
                    "name": ws_info["workspace_name"],
                    "bot": ws_info["bot_id"],
                    "admin": ws_info["admin_id"],
                },
                "id": payload["envelope_id"],
                "event": event["event"],
                "database": self._db,
            }
        )
        ev_type = event["event"]["type"]
        for module in self._modules.iterate_modules(ev_type):
            check_func = getattr(module["class"], f"check_{ev_type}")
            queue_name = check_func(context)
            if queue_name is not None:
                break
        else:
            await self._ack_queue.put((payload["envelope_id"], None))
            return False
        queue_name = f"{module['name']}/{queue_name}"
        api = SlackAPI(self._api_client, {"token": ws_info["workspace_token"]})
        await self._modules.queue(queue_name, module, api, context, self._ack_queue)
        return True
