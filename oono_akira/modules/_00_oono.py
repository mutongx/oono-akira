from oono_akira.modules import HandlerType, register
from oono_akira.slack import SlackContext


@register("/oono")
def handler(context: SlackContext, locked: bool) -> HandlerType:
    return process, {}


async def process(context: SlackContext):
    await context.ack()

    command = context.must_command()
    await context.api.chat.postEphemeral(
        {
            "channel": command.channel_id,
            "user": command.user_id,
            "text": "Hello from Oono Akira!",
            "blocks": [
                {
                    "type": "rich_text",
                    "elements": [
                        {"type": "rich_text_section", "elements": [{"type": "text", "text": "Hello from Oono Akira!"}]},
                        {
                            "type": "rich_text_list",
                            "style": "bullet",
                            "elements": [
                                {
                                    "type": "rich_text_section",
                                    "elements": [
                                        {"type": "text", "text": "Bot ID: "},
                                        {"type": "text", "text": context.workspace.botId},
                                    ],
                                },
                                {
                                    "type": "rich_text_section",
                                    "elements": [
                                        {"type": "text", "text": "Workspace ID: "},
                                        {"type": "text", "text": command.team_id},
                                    ],
                                },
                                {
                                    "type": "rich_text_section",
                                    "elements": [
                                        {"type": "text", "text": "Channel ID: "},
                                        {"type": "text", "text": command.channel_id},
                                    ],
                                },
                                {
                                    "type": "rich_text_section",
                                    "elements": [
                                        {"type": "text", "text": "User ID: "},
                                        {"type": "text", "text": command.user_id},
                                    ],
                                },
                                {
                                    "type": "rich_text_section",
                                    "elements": [
                                        {"type": "text", "text": "User is admin: "},
                                        {"type": "text", "text": str(command.user_id == context.workspace.adminId)},
                                    ],
                                },
                            ],
                        },
                        {
                            "type": "rich_text_preformatted",
                            "elements": [{"type": "text", "text": f"/oono {command.text}"}],
                        },
                    ],
                }
            ],
        }
    )
