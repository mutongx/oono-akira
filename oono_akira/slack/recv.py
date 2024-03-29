import sys
from dataclasses import dataclass, field, fields
from typing import Sequence, Optional, Type, TypeVar

from oono_akira.slack.any import AnyObject
from oono_akira.slack.block import Block


@dataclass
class SlackEventPayload:
    type: str
    user: str
    channel: str
    ts: str
    text: Optional[str] = None
    bot_id: Optional[str] = None
    thread_ts: Optional[str] = None
    blocks: Optional[Sequence[Block]] = None


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
            pending = None
            inferred_type = None
            if field.metadata:
                for (key, value), candidate_type in field.metadata.items():
                    if key in kwargs and kwargs[key] == value:
                        inferred_type = candidate_type
                        break
                else:
                    continue
            if getattr(inferred_type, "_name", None) == "Self":
                inferred_type = t
            unwrapped_type = field.type
            if isinstance(unwrapped_type, str):
                unwrapped_type = eval(unwrapped_type, vars(sys.modules[t.__module__]))
            if getattr(unwrapped_type, "_name", None) == "Optional":
                unwrapped_type = unwrapped_type.__args__[0]
            if getattr(unwrapped_type, "_name", None) == "Sequence":
                pending = []
                unwrapped_type = unwrapped_type.__args__[0]
            dst_type = inferred_type or unwrapped_type
            src_value = d[field.name]
            if hasattr(dst_type, "__dataclass_fields__"):
                if isinstance(pending, list):
                    assert isinstance(src_value, list)
                    for item in src_value:
                        pending.append(SlackPayloadParser._parse(dst_type, item))  # type: ignore
                else:
                    assert isinstance(src_value, dict)
                    pending = SlackPayloadParser._parse(dst_type, src_value)
            else:
                pending = d[field.name]
            kwargs[field.name] = pending
        return t(**kwargs)

    @staticmethod
    def parse(data: AnyObject) -> SlackWebSocketEventPayload:
        return SlackPayloadParser._parse(SlackWebSocketEventPayload, data)
