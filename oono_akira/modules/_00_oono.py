from oono_akira.modules import Handler, register
from oono_akira.admin import run_command
from oono_akira.slack.context import SlackContext


@register("/oono")
def handler(context: SlackContext, *_) -> Handler:
    return process, {}


async def process(context: SlackContext):
    await context.ack()
    await run_command(context, context.must_command().text)
