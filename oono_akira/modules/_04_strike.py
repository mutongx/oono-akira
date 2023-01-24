from oono_akira.modules import HandlerType, register
from oono_akira.slack import SlackContext


@register("message")
def handler(context: SlackContext) -> HandlerType:
    async def process(context: SlackContext):
        context["ack"]()
        event = context["event"]
        user_id = event["user"]
        if user_id == "USLACKBOT":
            return
        profile = await context["api"].users.info({"user": user_id})
        text = event["blocks"][0]["elements"][0]["elements"][0]["text"]
        body = {
            "channel": event["channel"],
            "text": f"( ｣ﾟДﾟ)｣＜ {profile['user']['profile']['display_name']} 刚才说了 {text}！",
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
        return "", process
