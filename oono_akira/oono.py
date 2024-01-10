import asyncio
import json
import ssl
import time
import traceback
from collections import deque
from contextlib import AsyncExitStack
from typing import Any, MutableMapping, Coroutine

from aiohttp import ClientSession, web, WSMsgType
from aiohttp.web_request import Request

from oono_akira.config import Configuration
from oono_akira.db import OonoDatabase
from oono_akira.log import log
from oono_akira.modules import ModulesManager
from oono_akira.slack.context import SlackContext
from oono_akira.slack.recv import SlackPayloadParser, SlackEventsApiPayload, SlackSlashCommandsPayload
from oono_akira.slack.send import SlackAPI


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

        self._db_config = config["database"]

        server = config["server"]
        if "ssl" in server:
            self._ssl_context = ssl.SSLContext()
            self._ssl_context.load_cert_chain(server["ssl"]["cert"], server["ssl"]["key"])
        else:
            self._ssl_context = None
        self._web_app = web.Application()
        self._web_app.add_routes([web.get(f"{server.get('prefix', '')}/oauth", self._oauth_handler)])
        self._web_app.add_routes([web.get(f"{server.get('prefix', '')}/install", self._install_handler)])
        self._web_port = server.get("port", 25472)

        self._payload_tracker: MutableMapping[str, str] = dict()
        self._payload_tracker_queue: deque[str] = deque()

        self._background_tasks: set[asyncio.Task[Any]] = set()

    async def __aenter__(self):
        self._ack_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async with AsyncExitStack() as stack:
            self._db = await stack.enter_async_context(OonoDatabase(self._db_config))
            self._client = await stack.enter_async_context(ClientSession())
            self._modules = await stack.enter_async_context(ModulesManager())
            self._stack = stack.pop_all()

        # server
        self._web_runner = web.AppRunner(self._web_app)
        await self._web_runner.setup()
        self._web_site = web.TCPSite(self._web_runner, port=self._web_port, ssl_context=self._ssl_context)
        await self._web_site.start()
        log(f"Listening on port {self._web_port}")

        return self

    async def __aexit__(self, *_):
        await self._web_site.stop()
        await self._web_runner.cleanup()
        await self._stack.aclose()

    async def _oauth_handler(self, request: Request):
        code = request.rel_url.query["code"]
        auth_resp = await SlackAPI(self._client).oauth.v2.access(code=code, **self._slack_oauth)
        if not auth_resp["ok"]:
            return web.Response(text=auth_resp["error"])
        await self._db.setup_workspace(
            auth_resp["team"]["id"],
            auth_resp["team"]["name"],
            auth_resp["bot_user_id"],
            auth_resp["authed_user"]["id"],
            auth_resp["access_token"],
            auth_resp["incoming_webhook"]["url"],
        )
        self._run_in_background(self._db.record_payload("oauth", auth_resp))
        log(f"App is installed in workspace {auth_resp['team']['name']}, id = {auth_resp['team']['id']}")
        test_resp = await SlackAPI(self._client, token=auth_resp["access_token"]).auth.test()
        return web.HTTPFound(test_resp["url"])

    async def _install_handler(self, _: Request):
        auth_uri = "https://slack.com/oauth/v2/authorize?client_id={}&scope={}&redirect_uri={}".format(
            self._slack_oauth["client_id"],
            ",".join(self._slack_permissions),
            self._slack_oauth["redirect_uri"],
        )
        raise web.HTTPFound(auth_uri)

    def _run_in_background(self, coro: Coroutine[Any, Any, Any]):
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def run(self):
        while True:
            try:
                log("Trying to establish connection")
                conn_resp = await self._client.post(
                    "https://slack.com/api/apps.connections.open",
                    headers={"Authorization": f"Bearer {self._slack_app_token}"},
                )
                if not conn_resp.ok:
                    log("Failed to request connections.open, retrying...")
                    time.sleep(5)
                    continue

                conn_url = await conn_resp.json()
                if not conn_url["ok"]:
                    log(f"connections.open() returned error: {conn_url['error']}, retrying...")
                    time.sleep(5)
                    continue

                async with self._client.ws_connect(conn_url["url"]) as conn:
                    recv = asyncio.create_task(conn.receive())
                    ack = asyncio.create_task(self._ack_queue.get())
                    pending = {recv, ack}
                    while True:
                        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                        if recv in done:
                            # Receive data
                            recv_result = await recv
                            if recv_result.type == WSMsgType.ERROR:
                                log(f"Websocket returned error: {recv_result}")
                                break
                            self._run_in_background(self._db.record_payload("websocket", recv_result.data))
                            # Start a new recv task
                            recv = asyncio.create_task(conn.receive())
                            pending.add(recv)
                            # Process payload
                            payload = SlackPayloadParser.parse(json.loads(recv_result.data))
                            if payload.type == "hello":
                                assert payload.connection_info is not None
                                log(f"WebSocket connection established, appid = {payload.connection_info['app_id']}")
                            elif payload.type == "disconnect":
                                assert payload.reason is not None
                                log(f"Received disconnect request, reason: {payload.reason}")
                                await conn.close()
                                break
                            elif payload.type == "events_api":
                                assert payload.envelope_id is not None
                                assert isinstance(payload.payload, SlackEventsApiPayload)
                                envelope_id = payload.envelope_id
                                event_id = payload.payload.event_id
                                track = self._track_payload(event_id, "unknown")
                                if track is None:
                                    handler_name = await self._process_event(envelope_id, payload.payload)
                                    self._track_payload(event_id, handler_name, update=True)
                                    log(f"Handled event {event_id}, handler={handler_name}")
                                else:
                                    log(f"Duplicate event {event_id}. Previously processed by {track}.")
                            elif payload.type == "slash_commands":
                                assert payload.envelope_id is not None
                                assert isinstance(payload.payload, SlackSlashCommandsPayload)
                                envelope_id = payload.envelope_id
                                handler_name = await self._process_command(envelope_id, payload.payload)
                                log(f"Handled command {payload.payload.command}, handler={handler_name}")
                        if ack in done:
                            # Start a new ack task
                            ack_result = await ack
                            ack = asyncio.create_task(self._ack_queue.get())
                            pending.add(ack)
                            # Process ack
                            envelope_id, payload = ack_result
                            self._run_in_background(conn.send_json({"envelope_id": envelope_id, "payload": payload}))
                log(f"Disconnected.")

            except Exception:
                traceback.print_exc()

    def _track_payload(self, track_id: str, processor: str, *, update: bool = False) -> str | None:
        # When update is True, we should never add new values to tracker
        if update:
            if track_id in self._payload_tracker:
                self._payload_tracker[track_id] = processor
            return
        # The payload is already tracked, so return the value
        if track_id in self._payload_tracker:
            return self._payload_tracker[track_id]
        # Otherwise, we add a record
        self._payload_tracker_queue.append(track_id)
        self._payload_tracker[track_id] = processor
        if len(self._payload_tracker_queue) > self.PAYLOAD_TRACKER_SIZE:
            item = self._payload_tracker_queue.popleft()
            del self._payload_tracker[item]
        return

    async def _process_event(self, envelope_id: str, payload: SlackEventsApiPayload) -> str:
        async def ack(body: Any = None):
            return await self._ack_queue.put((envelope_id, body))

        workspace = await self._db.get_workspace(payload.team_id)
        if workspace is None:
            await ack()
            return "unknown_workspace"
        if payload.event.user == workspace.botId:
            await ack()
            return "ignore_self"
        if payload.event.user == "USLACKBOT":
            await ack()
            return "ignore_slackbot"

        context = SlackContext(
            id=envelope_id,
            api=SlackAPI(self._client, workspace.token),
            db=self._db,
            ack=ack,
            workspace=workspace,
            event=payload.event,
        )

        locks, accesses = await asyncio.gather(
            self._db.get_locks(workspace.id, payload.event.channel),
            self._db.get_accesses(workspace.id, payload.event.channel, payload.event.user),
        )
        for module, constructor in self._modules.iterate_modules(payload.event.type):
            if locks and module not in locks:
                continue
            handler = constructor(context, {"is_locked": module in locks, "has_access": module in accesses})
            if handler is not None:
                break
        else:
            await ack()
            return "no_handler"

        async def callback():
            if "lock" in option:
                if option["lock"]:
                    await self._db.acquire_lock(workspace.id, payload.event.channel, module)
                else:
                    await self._db.release_lock(workspace.id, payload.event.channel, module)

        handler_func, option = handler
        queue_name = f"{handler_func.__module__}/{option.get('queue', '__default__')}"
        await self._modules.queue(queue_name, context, handler_func, callback)

        return handler_func.__module__

    async def _process_command(self, envelope_id: str, payload: SlackSlashCommandsPayload) -> str:
        async def ack(body: Any = None):
            return await self._ack_queue.put((envelope_id, body))

        workspace = await self._db.get_workspace(payload.team_id)
        if workspace is None:
            await ack()
            return "unknown_workspace"

        context = SlackContext(
            id=envelope_id,
            api=SlackAPI(self._client, workspace.token),
            db=self._db,
            ack=ack,
            workspace=workspace,
            command=payload,
        )

        locks, accesses = await asyncio.gather(
            self._db.get_locks(workspace.id, payload.channel_id),
            self._db.get_accesses(workspace.id, payload.channel_id, payload.user_id),
        )
        for module, constructor in self._modules.iterate_modules(payload.command):
            handler = constructor(context, {"is_locked": module in locks, "has_access": module in accesses})
            if handler is not None:
                break
        else:
            await ack()
            return "no_handler"

        handler_func, option = handler
        queue_name = f"{handler_func.__module__}/{option.get('queue', '__default__')}"
        await self._modules.queue(queue_name, context, handler_func)

        return handler_func.__module__
