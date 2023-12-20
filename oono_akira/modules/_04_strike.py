from typing import cast

from oono_akira.modules import Handler, register
from oono_akira.slack import SlackContext
from oono_akira.slack.common import RichTextSpan


@register("message")
def handler(context: SlackContext, *_) -> Handler:
    event = context.must_event()
    if event.bot_id:
        return
    blocks = event.blocks
    if not blocks or len(blocks) != 1:
        return
    block = blocks[0]
    if block.type != "rich_text":
        return
    if not block.elements or len(block.elements) != 1:
        return
    section = block.elements[0]
    if len(section.elements) != 1:
        return
    element = cast(RichTextSpan, section.elements[0])
    if not element.style or not element.style.strike:
        return
    if not element.text:
        return
    context.data = element.text
    return process, {}


async def process(context: SlackContext):
    await context.ack()
    event = context.must_event()
    user_id = event.user
    if user_id == "USLACKBOT":
        return
    profile = await context.api.users.info({"user": user_id})
    body = {
        "channel": event.channel,
        "text": f"( ｣ﾟДﾟ)｣＜ {profile['user']['profile']['display_name']} 刚才说了 {context.data}！",
    }
    if event.thread_ts:
        body["thread_ts"] = event.thread_ts
    await context.api.chat.postMessage(body)
