from dataclasses import dataclass, field, fields
from typing import Any, Optional, Type, TypeVar

from oono_akira.slack.common import AnyObject


@dataclass
class SlackEventPayload:
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
    type: str
    team_id: str
    event_id: str
    event: SlackEventPayload


@dataclass
class SlackSlashCommandsPayload:
    team_id: str
    channel_id: str
    user_id: str
    command: str
    text: str
    response_url: str


@dataclass
class SlackWebSocketEventPayload:
    type: str
    envelope_id: Optional[str] = None
    payload: Optional[SlackEventsApiPayload | SlackSlashCommandsPayload] = field(
        default=None,
        metadata={
            ("type", "events_api"): SlackEventsApiPayload,
            ("type", "slash_commands"): SlackSlashCommandsPayload,
        },
    )
    accepts_response_payload: Optional[bool] = None
    connection_info: Optional[AnyObject] = None
    debug_info: Optional[AnyObject] = None
    reason: Optional[str] = None


class SlackPayloadParser:
    T = TypeVar("T")

    @staticmethod
    def _parse(t: Type[T], d: AnyObject) -> T:
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
    def parse(data: AnyObject) -> SlackWebSocketEventPayload:
        return SlackPayloadParser._parse(SlackWebSocketEventPayload, data)
