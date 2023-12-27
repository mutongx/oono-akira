from oono_akira.modules import Handler, register
from oono_akira.admin import run_command
from oono_akira.slack.context import SlackContext


@register("/oono")
def handler(context: SlackContext, *_) -> Handler:
    return process, {}


async def process(context: SlackContext):
    await context.ack()

    command = context.must_command()
    await run_command(context, command.team_id, command.channel_id, command.user_id, command.text)
