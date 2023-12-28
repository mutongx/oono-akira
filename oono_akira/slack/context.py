from dataclasses import dataclass
from typing import Any, Awaitable, Protocol

from prisma.models import Workspace

from oono_akira.db import OonoDatabase
from oono_akira.slack.send import SlackAPI
from oono_akira.slack.recv import SlackEventPayload, SlackSlashCommandsPayload


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
    event: SlackEventPayload | None = None
    command: SlackSlashCommandsPayload | None = None
    data: Any = None

    def must_event(self):
        if self.event is None:
            raise RuntimeError("event is None")
        return self.event

    def must_command(self):
        if self.command is None:
            raise RuntimeError("command is None")
        return self.command

    def reply_args(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if self.event:
            result["channel"] = self.event.channel
            if self.event.thread_ts:
                result["thread_ts"] = self.event.thread_ts
        if self.command:
            result["channel"] = self.command.channel_id
            result["user"] = self.command.user_id
        return result
