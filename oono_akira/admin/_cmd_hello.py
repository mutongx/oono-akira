from argparse import ArgumentParser, Namespace

from oono_akira.slack.context import SlackContext
from oono_akira.slack.block import Block, RichTextElement, RichTextSpan
from oono_akira.admin import CommandResponse


def help():
    return "Say hello to Oono Akira"


def setup(parser: ArgumentParser):
    parser.description = "Say hello to Oono Akira! She will give you some useful information."


async def handler(context: SlackContext | None, args: Namespace) -> CommandResponse:
    if context is None:
        return "message", "Hello from Oono Akira!", []
    command = context.must_command()
    block = Block(
        type="rich_text",
        elements=[
            RichTextElement(
                type="rich_text_section",
                elements=[
                    RichTextSpan(type="text", text="Hello from Oono Akira!\n"),
                ],
            ),
            RichTextElement(
                type="rich_text_list",
                style="bullet",
                elements=[
                    RichTextElement(
                        type="rich_text_section",
                        elements=[
                            RichTextSpan(type="text", text="Bot ID: "),
                            RichTextSpan(type="text", text=context.workspace.botId),
                        ],
                    ),
                    RichTextElement(
                        type="rich_text_section",
                        elements=[
                            RichTextSpan(type="text", text="Workspace ID: "),
                            RichTextSpan(type="text", text=command.team_id),
                        ],
                    ),
                    RichTextElement(
                        type="rich_text_section",
                        elements=[
                            RichTextSpan(type="text", text="Channel ID: "),
                            RichTextSpan(type="text", text=command.channel_id),
                        ],
                    ),
                    RichTextElement(
                        type="rich_text_section",
                        elements=[
                            RichTextSpan(type="text", text="User ID: "),
                            RichTextSpan(type="text", text=command.user_id),
                        ],
                    ),
                    RichTextElement(
                        type="rich_text_section",
                        elements=[
                            RichTextSpan(type="text", text="User is admin: "),
                            RichTextSpan(type="text", text=str(command.user_id == context.workspace.adminId)),
                        ],
                    ),
                ],
            ),
        ],
    )
    return "message", "Hello from Oono Akira!", [block]
