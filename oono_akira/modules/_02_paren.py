from typing import Optional
from oono_akira.modules.__base__ import ModuleBase
from oono_akira.slack import SlackContext

class Paren(ModuleBase):

    _L = "([{（［｛⦅〚⦃“‘‹«「〈《【〔⦗『〖〘｢⟦⟨⟪⟮⟬⌈⌊⦇⦉❛❝❨❪❴❬❮❰❲⏜⎴⏞⏠﹁﹃︹︻︗︿︽﹇︷"
    _R = ")]}）］｝⦆〛⦄”’›»」〉》】〕⦘』〗〙｣⟧⟩⟫⟯⟭⌉⌋⦈⦊❜❞❩❫❵❭❯❱❳⏝⎵⏟⏡﹂﹄︺︼︘﹀︾﹈︸"
    _MAPPING = {
        l: r for l, r in zip(_L, _R)
    }

    @staticmethod
    def check_message(context: SlackContext) -> Optional[str]:
        text = context["event"].get("text")
        if not text:
            return
        stack = []
        for char in text:
            if char in Paren._MAPPING:
                stack.append(Paren._MAPPING[char])
            elif stack and stack[-1] == char:
                stack.pop()
        if stack:
            context["paren_stack"] = stack
            return ""

    async def process(self):
        event = self._slack_context["event"]
        body = {
            "channel": event["channel"],
            "text": "".join(reversed(self._slack_context["paren_stack"])) + " ○(￣^￣○)",
        }
        if "thread_ts" in event:
            body["thread_ts"] = event["thread_ts"]
        await self._slack_api.chat.postMessage(body)

MODULE = Paren
