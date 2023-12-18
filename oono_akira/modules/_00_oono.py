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
            "text": "\n".join(
                [
                    "Hello from Oono Akira!",
                    "",
                    f"Bot ID: {context.workspace.botId}",
                    f"Workspace ID: {command.team_id}",
                    f"Channel ID: {command.channel_id}",
                    f"User ID: {command.user_id}",
                    f"User is admin: {command.user_id == context.workspace.adminId}",
                ]
            ),
        }
    )
