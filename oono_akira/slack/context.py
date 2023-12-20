from dataclasses import dataclass
from typing import Any, Awaitable, Optional, Protocol

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
    event: Optional[SlackEventPayload] = None
    command: Optional[SlackSlashCommandsPayload] = None
    data: Any = None

    def must_event(self):
        if self.event is None:
            raise RuntimeError("event is None")
        return self.event

    def must_command(self):
        if self.command is None:
            raise RuntimeError("command is None")
        return self.command
