from typing import cast

from oono_akira.modules import HandlerType, register
from oono_akira.slack import SlackContext


class StrikeContext(SlackContext):
    striked_text: str


@register("message")
def handler(context: SlackContext) -> HandlerType:
    async def process(context: SlackContext):
        context = cast(StrikeContext, context)
        await context["ack"]()
        event = context["event"]
        user_id = event["user"]
        if user_id == "USLACKBOT":
            return
        profile = await context["api"].users.info({"user": user_id})
        body = {
            "channel": event["channel"],
            "text": f"( ｣ﾟДﾟ)｣＜ {profile['user']['profile']['display_name']} 刚才说了 {context['striked_text']}！",
        }
        if "thread_ts" in event:
            body["thread_ts"] = event["thread_ts"]
        await context["api"].chat.postMessage(body)

    blocks = context["event"].get("blocks")
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
        context = cast(StrikeContext, context)
        context["striked_text"] = blocks[0]["elements"][0]["elements"][0]["text"]
        return "", process
