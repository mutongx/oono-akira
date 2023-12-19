from oono_akira.modules import Handler, register
from oono_akira.slack import SlackContext


@register("message")
def handler(context: SlackContext, *_) -> Handler:
    event = context.must_event()
    if event.bot_id:
        return
    blocks = event.blocks
    if not blocks or len(blocks) != 1:
        return
    block = blocks[0]
    elements = block.get("elements")
    if not elements or len(elements) != 1:
        return
    elements = elements[0].get("elements")
    if not elements or len(elements) != 1:
        return
    element = elements[0]
    if element.get("style", {}).get("strike"):
        context.data = blocks[0]["elements"][0]["elements"][0]["text"]
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
