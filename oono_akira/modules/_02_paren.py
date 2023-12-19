import re
from typing import List

from oono_akira.modules import HandlerType, register
from oono_akira.slack import SlackContext

_L = "([{（［｛⦅〚⦃“‘‹«「〈《【〔⦗『〖〘｢⟦⟨⟪⟮⟬⌈⌊⦇⦉❛❝❨❪❴❬❮❰❲⏜⎴⏞⏠⎛⎜⎝﹁﹃︹︻︗︿︽﹇︷9"
_R = ")]}）］｝⦆〛⦄”’›»」〉》】〕⦘』〗〙｣⟧⟩⟫⟯⟭⌉⌋⦈⦊❜❞❩❫❵❭❯❱❳⏝⎵⏟⏡⎞⎟⎠﹂﹄︺︼︘﹀︾﹈︸0"

assert len(_L) == len(_R)

PAREN_MAPPING = {l: r for l, r in zip(_L, _R)}


@register("message")
def handler(context: SlackContext, locked: bool) -> HandlerType:
    event = context.must_event()
    if event.bot_id:
        return
    if not event.text:
        return
    stack: List[str] = []
    for char in re.sub(r"<@[0-9A-Za-z]+>", "", event.text):
        if char in PAREN_MAPPING:
            stack.append(PAREN_MAPPING[char])
        elif stack and stack[-1] == char:
            stack.pop()
    if not stack:
        return
    context.data = stack
    return process, {}


async def process(context: SlackContext):
    await context.ack()
    event = context.must_event()
    body = {
        "channel": event.channel,
        "text": "".join(reversed(context.data)) + " ○(￣^￣○)",
    }
    if event.thread_ts:
        body["thread_ts"] = event.thread_ts
    await context.api.chat.postMessage(body)
