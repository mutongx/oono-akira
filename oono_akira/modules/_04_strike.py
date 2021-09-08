from oono_akira.modules.__base__ import ModuleBase
from oono_akira.slack import SlackContext

class Strike(ModuleBase):

    @staticmethod
    def check_message(context: SlackContext):
        blocks = context["event"].get("blocks")
        if not blocks or len(blocks) != 1:
            return False
        block = blocks[0]
        elements = block.get("elements")
        if not elements or len(elements) != 1:
            return False
        elements = elements[0].get("elements")
        if not elements or len(elements) != 1:
            return False
        element = elements[0]
        if element.get("style", {}).get("strike"):
            return True

    async def process(self):
        event = self._slack_context["event"]
        user_id = event["user"]
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
