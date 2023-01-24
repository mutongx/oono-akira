from oono_akira.slack import SlackContext, SlackAPI
from oono_akira.modules import register, HandlerType


_L = "([{（［｛⦅〚⦃“‘‹«「〈《【〔⦗『〖〘｢⟦⟨⟪⟮⟬⌈⌊⦇⦉❛❝❨❪❴❬❮❰❲⏜⎴⏞⏠﹁﹃︹︻︗︿︽﹇︷"
_R = ")]}）］｝⦆〛⦄”’›»」〉》】〕⦘』〗〙｣⟧⟩⟫⟯⟭⌉⌋⦈⦊❜❞❩❫❵❭❯❱❳⏝⎵⏟⏡﹂﹄︺︼︘﹀︾﹈︸"

assert len(_L) == len(_R)

PAREN_MAPPING = {l: r for l, r in zip(_L, _R)}


@register("message")
def handler(context: SlackContext) -> HandlerType:
    async def process(context: SlackContext, api: SlackAPI):
        event = context["event"]
        body = {
            "channel": event["channel"],
            "text": "".join(reversed(context["paren_stack"])) + " ○(￣^￣○)",
        }
        if "thread_ts" in event:
            body["thread_ts"] = event["thread_ts"]
        await api.chat.postMessage(body)

    text = context["event"].get("text")
    if not text:
        return
    stack = []
    for char in text:
        if char in PAREN_MAPPING:
            stack.append(PAREN_MAPPING[char])
        elif stack and stack[-1] == char:
            stack.pop()
    if stack:
        context["paren_stack"] = stack
        return "", process
