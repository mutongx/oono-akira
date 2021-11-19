from typing import Optional, Union
from oono_akira.modules.__base__ import ModuleBase
from oono_akira.slack import SlackContext

class Strike(ModuleBase):

    @staticmethod
    def check_message(context: SlackContext) -> Optional[str]:
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
            return ""

    async def process(self):
        event = self._slack_context["event"]
        user_id = event["user"]
        if user_id == "USLACKBOT":
            return
        profile = await self._slack_api.users.info({"user": user_id})
        text = event["blocks"][0]["elements"][0]["elements"][0]["text"]
        body = {
            "channel": event["channel"],
            "text": f"( ｣ﾟДﾟ)｣＜ {profile['user']['profile']['display_name']} 刚才说了 {text}！",
        }
        if "thread_ts" in event:
            body["thread_ts"] = event["thread_ts"]
        await self._slack_api.chat.postMessage(body)

MODULE = Strike
