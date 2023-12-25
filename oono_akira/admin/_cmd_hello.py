from argparse import ArgumentParser, Namespace

from oono_akira.slack.context import SlackContext
from oono_akira.slack.send import SlackPayloadDumper
from oono_akira.slack.block import Block, RichTextElement, RichTextSpan


def help():
    return "Say hello to Oono Akira"


def setup(parser: ArgumentParser):
    parser.description = "Say hello to Oono Akira! She will give you some useful information."


async def handler(context: SlackContext | None, args: Namespace):
    if context is None:
        return
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
    await context.api.chat.postEphemeral(
        {
            "channel": command.channel_id,
            "user": command.user_id,
            "text": "Hello from Oono Akira!",
            "blocks": [SlackPayloadDumper.dump(block)],
        }
    )
