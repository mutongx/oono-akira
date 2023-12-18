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
                    f"Self: {context.workspace.botId}",
                    f"Workspace: {command.team_id}",
                    f"Channel: {command.channel_id}",
                    f"User: {command.user_id}",
                ]
            ),
        }
    )
