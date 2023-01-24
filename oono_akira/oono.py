import asyncio
import ssl
import json
import time
import traceback
from contextlib import AsyncExitStack
from collections import deque
from typing import Deque, Dict, Tuple, Any, Optional

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
        self._payload_mapping: Dict[str, Optional[str]] = dict()

    async def __aenter__(self):

        # database
        self._db.initialize()

        self._ack_queue: asyncio.Queue[Tuple[str, str, Any]] = asyncio.Queue()

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
        log(f"Listening on port {self._web_port}")

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
        log(
            f"App is installed in workspace {resp['team']['name']}, id = {resp['team']['idT']}"
        )
        return web.Response(text="Done")

    async def _install_handler(self, _: Request):
        auth_uri = "https://slack.com/oauth/v2/authorize?client_id={}&scope={}&redirect_uri={}".format(
            self._slack_oauth["client_id"],
            ",".join(self._slack_permissions),
            self._slack_oauth["redirect_uri"],
        )
        log(f"Requesting /install, uri = {auth_uri}", debug=True)
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
                                event_id = payload["payload"]["event_id"]
                                envelope_id = payload["envelope_id"]
                                log(
                                    f"Received event  {event_id}, envelope_id={envelope_id}"
                                )
                                track = self._track_payload(event_id)
                                if track is not True:
                                    if track is not None:
                                        log(
                                            f"Duplicate event {event_id}. Previously processed by {track}."
                                        )
                                    else:
                                        log(f"Duplicate event {event_id}.")
                                else:
                                    handler_name = await self._process_event(payload)
                                    self._track_payload(event_id, handler_name, True)
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
                            envelope_id, event_id, ack_payload = ack_result
                            ack_str = json.dumps(
                                {"envelope_id": envelope_id, "payload": ack_payload}
                            )
                            asyncio.create_task(conn.send(ack_str))
                            log(
                                f"Acking event    {event_id}, envelope_id={envelope_id}",
                                debug=True,
                            )
                log(f"Disconnected.")

            except Exception:
                traceback.print_exc()

    def _track_payload(
        self, track_id: str, processor: Optional[str] = None, update: bool = False
    ) -> bool | str | None:
        if update:
            if track_id not in self._payload_mapping:
                return False
            self._payload_mapping[track_id] = processor
            return True
        # update == False
        if track_id in self._payload_mapping:
            return self._payload_mapping[track_id]
        self._payload_queue.append(track_id)
        self._payload_mapping[track_id] = processor
        if len(self._payload_queue) > self.PAYLOAD_TRACKER_SIZE:
            item = self._payload_queue.popleft()
            del self._payload_mapping[item]
        return True

    async def _process_event(self, payload: Any) -> str:
        def ack_func(body: Any = None):
            return self._ack_queue.put(
                (payload["envelope_id"], payload["payload"]["event_id"], body)
            )

        event = payload["payload"]["event"]
        ws_info = self._db.get_workspace_info(payload["payload"]["team_id"])

        # Ignore if event payload is me
        if event.get("user") == ws_info["bot_id"]:
            await ack_func()
            return "ignore_self"

        # Prepare context
        context: SlackContext = {
            "api": SlackAPI(self._api_client, ws_info["workspace_token"]),
            "database": self._db,
            "ack": ack_func,
            "workspace": {
                "name": ws_info["workspace_name"],
                "bot_id": ws_info["bot_id"],
                "admin_id": ws_info["admin_id"],
            },
            "id": payload["envelope_id"],
            "event": event,
        }

        # Find handler function
        for constructor in self._modules.iterate_modules(event["type"]):
            handler = constructor(context)
            if handler is not None:
                break
        else:
            await ack_func()
            print(payload)
            return "no_handler"

        # Enqueue the function
        queue_name, handler_func = handler
        queue_name = f"{handler_func.__module__}/{queue_name}"
        await self._modules.queue(queue_name, context, handler_func)

        return handler_func.__module__
