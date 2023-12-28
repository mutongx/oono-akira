import re
from typing import MutableSequence

from oono_akira.modules import Handler, HandlerConstructorOption, register
from oono_akira.slack.context import SlackContext

_L = "([{（［｛⦅〚⦃“‘‹«「〈《【〔⦗『〖〘｢⟦⟨⟪⟮⟬⌈⌊⦇⦉❛❝❨❪❴❬❮❰❲⏜⎴⏞⏠⎛⎜⎝﹁﹃︹︻︗︿︽﹇︷9"
_R = ")]}）］｝⦆〛⦄”’›»」〉》】〕⦘』〗〙｣⟧⟩⟫⟯⟭⌉⌋⦈⦊❜❞❩❫❵❭❯❱❳⏝⎵⏟⏡⎞⎟⎠﹂﹄︺︼︘﹀︾﹈︸0"

assert len(_L) == len(_R)

PAREN_MAPPING = {l: r for l, r in zip(_L, _R)}


@register("message")
def handler(context: SlackContext, option: HandlerConstructorOption) -> Handler:
    if not option["has_access"]:
        return
    event = context.must_event()
    if event.bot_id:
        return
    if not event.text:
        return
    stack: MutableSequence[str] = []
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
    await context.api.chat.postMessage(
        {
            **context.reply_args(),
            "text": "".join(reversed(context.data)) + " ○(￣^￣○)",
        }
    )
