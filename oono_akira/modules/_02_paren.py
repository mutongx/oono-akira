from typing import List, cast

from oono_akira.slack import SlackContext
from oono_akira.modules import register, HandlerType


_L = "([{（［｛⦅〚⦃“‘‹«「〈《【〔⦗『〖〘｢⟦⟨⟪⟮⟬⌈⌊⦇⦉❛❝❨❪❴❬❮❰❲⏜⎴⏞⏠﹁﹃︹︻︗︿︽﹇︷"
_R = ")]}）］｝⦆〛⦄”’›»」〉》】〕⦘』〗〙｣⟧⟩⟫⟯⟭⌉⌋⦈⦊❜❞❩❫❵❭❯❱❳⏝⎵⏟⏡﹂﹄︺︼︘﹀︾﹈︸"

assert len(_L) == len(_R)

PAREN_MAPPING = {l: r for l, r in zip(_L, _R)}


class ParenContext(SlackContext):
    paren_stack: List[str]


@register("message")
def handler(context: SlackContext) -> HandlerType:
    async def process(context: SlackContext):
        await context["ack"]()
        context = cast(ParenContext, context)
        event = context["event"]
        body = {
            "channel": event["channel"],
            "text": "".join(reversed(context["paren_stack"])) + " ○(￣^￣○)",
        }
        if "thread_ts" in event:
            body["thread_ts"] = event["thread_ts"]
        await context["api"].chat.postMessage(body)

    text = context["event"].get("text")
    if not text:
        return
    stack: List[str] = []
    for char in text:
        if char in PAREN_MAPPING:
            stack.append(PAREN_MAPPING[char])
        elif stack and stack[-1] == char:
            stack.pop()
    if not stack:
        return
    context = cast(ParenContext, context)
    context["paren_stack"] = stack
    return "", process
