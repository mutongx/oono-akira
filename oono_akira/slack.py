from dataclasses import dataclass, field, fields
from typing import Any, Awaitable, Dict, Optional, Protocol, Tuple, Type, TypeVar

from aiohttp import ClientSession

from prisma.models import Workspace

from oono_akira.db import OonoDatabase
from oono_akira.log import log


DataclassType = TypeVar("DataclassType")

AnyDict = Dict[Any, Any]


@dataclass
class SlackEvent:
    type: str
    user: str
    channel: str
    ts: str
    text: Optional[str] = None
    bot_id: Optional[str] = None
    thread_ts: Optional[str] = None
    blocks: Optional[Any] = None


@dataclass
class SlackEventsApiPayload:
    team_id: str
    event_id: str
    event: SlackEvent


@dataclass
class SlackSlashCommandsPayload:
    team_id: str
    channel_id: str
    user_id: str
    command: str
    text: str
    response_url: str


@dataclass
class SlackWebsocketConnectionInfoPayload:
    app_id: str


@dataclass
class SlackWebSocketEventPayload:
    type: str
    payload: Optional[SlackEventsApiPayload | SlackSlashCommandsPayload] = field(
        default=None,
        metadata={
            ("type", "events_api"): SlackEventsApiPayload,
            ("type", "slash_commands"): SlackSlashCommandsPayload,
        },
    )
    envelope_id: Optional[str] = None
    accepts_response_payload: Optional[bool] = None
    connection_info: Optional[SlackWebsocketConnectionInfoPayload] = None
    reason: Optional[str] = None


class SlackPayloadParser:
    @staticmethod
    def _parse(t: Type[DataclassType], d: AnyDict) -> DataclassType:
        kwargs = {}
        for field in fields(t):  # type: ignore
            if field.name not in d:
                continue
            real_type = field.type
            if field.metadata:
                for (key, value), candidate_type in field.metadata.items():
                    if key in kwargs and kwargs[key] == value:
                        real_type = candidate_type
                        break
                else:
                    continue
            elif getattr(field.type, "_name", None) == "Optional":
                real_type = field.type.__args__[0]
            if hasattr(real_type, "__dataclass_fields__"):
                kwargs[field.name] = SlackPayloadParser._parse(real_type, d[field.name])
            else:
                kwargs[field.name] = d[field.name]
        return t(**kwargs)

    @staticmethod
    def parse(data: AnyDict) -> SlackWebSocketEventPayload:
        return SlackPayloadParser._parse(SlackWebSocketEventPayload, data)


class SlackAPI:
    _REQ = {
        "oauth.v2.access": {
            "method": "post",
            "mime": "application/x-www-form-urlencoded",
        },
        "users.info": {
            "method": "get",
        },
    }

    def __init__(
        self,
        session: ClientSession,
        token: Optional[str] = None,
        path: Tuple[str, ...] = tuple(),
    ):
        self._session = session
        self._token = token
        self._path = path

    def __getattr__(self, key: str):
        return SlackAPI(self._session, self._token, self._path + (key,))

    async def __call__(self, __data: Optional[AnyDict] = None, **kwargs: Any) -> Any:
        # Prepare request payload
        payload: AnyDict = dict(**__data if __data else {}, **kwargs)
        headers: AnyDict = {}
        # Prepare request argument
        api = ".".join(self._path)
        req = self._REQ.get(api, {})
        method = req.get("method", "post")
        body = {}
        if method == "post":
            mime = req.get("mime", "application/json")
            headers = {"Content-Type": f"{mime}; charset=UTF-8"}
            if mime == "application/x-www-form-urlencoded":
                body["data"] = payload
            elif mime == "application/json":
                body["json"] = payload
        elif method == "get":
            body["params"] = payload
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        # Send request
        resp = await self._session.request(method, f"https://slack.com/api/{api}", headers=headers, **body)
        result = await resp.json()
        if not result.get("ok"):
            log(f"Error: {result}")
        return result


class SlackAckFunction(Protocol):
    def __call__(self, body: Any = ..., /) -> Awaitable[None]:
        ...


@dataclass
class SlackContext:
    id: str
    api: SlackAPI
    db: OonoDatabase
    ack: SlackAckFunction
    workspace: Workspace
    event: SlackEvent
    data: Any = None
