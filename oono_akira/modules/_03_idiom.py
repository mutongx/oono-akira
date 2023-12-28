import asyncio
import json
import random
import unicodedata
from collections import defaultdict
from typing import Any

import aiohttp
from oono_akira.modules import Handler, HandlerConstructorOption, register
from oono_akira.slack.context import SlackContext

dict_data_url = "https://github.com/pwxcoo/chinese-xinhua/raw/master/data/idiom.json"
dict_data = None


async def fetch_dict_data():
    global dict_data
    if dict_data is None:
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(dict_data_url) as resp:
                text = await resp.text()
        raw = json.loads(text)
        new_data: Any = {
            "begin": defaultdict(list),
            "end": defaultdict(list),
            "mapping": {},
            "list": [],
        }
        for item in raw:
            pinyin = item["pinyin"].split()
            if len(pinyin) != 4:
                continue
            pinyin = list(
                map(
                    lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode(),
                    pinyin,
                )
            )
            item["pinyin_normalized"] = pinyin
            begin = pinyin[0]
            end = pinyin[-1]
            new_data["begin"][begin].append(item)
            new_data["end"][end].append(item)
            new_data["mapping"][item["word"]] = item
            new_data["list"].append(item)
        dict_data = new_data
    return dict_data


@register("message")
def handler(context: SlackContext, option: HandlerConstructorOption) -> Handler:
    if not option["has_access"]:
        return
    event = context.must_event()
    if event.bot_id:
        return
    if not event.text:
        return
    channel = event.channel
    if not option["is_locked"]:
        if event.text == "成语接龙":
            asyncio.create_task(fetch_dict_data())
            return process, {"queue": channel, "lock": True}
    else:
        if event.text == "不玩了":
            return process, {"queue": channel, "lock": False}
        else:
            return process, {"queue": channel}


async def process(context: SlackContext):
    await context.ack()
    event = context.must_event()
    text = event.text
    channel = event.channel
    dictionary = await fetch_dict_data()

    response_word = None
    response_text = None
    response_quote = None
    response_react = None

    async with context.db.get_session(game="idiom", workspace=context.workspace.id, channel=channel) as session:
        if text == "成语接龙":
            response_word = random.choice(dictionary["list"])
            session["word"] = response_word
        elif text == "不玩了":
            response_text = "祝你身体健康"
            session.clear()
        elif text == "不会":
            begin = session["word"]["pinyin_normalized"][-1]
            if begin not in dictionary["begin"]:
                response_text = "草，我也不会"
                session.clear()
            else:
                response_word = random.choice(dictionary["begin"][begin])
                session["word"] = response_word
        else:
            user_word = dictionary["mapping"].get(text)
            if user_word is None:
                response_react = "x"
            elif user_word["pinyin_normalized"][0] != session["word"]["pinyin_normalized"][-1]:
                response_react = "x"
            else:
                begin = user_word["pinyin_normalized"][-1]
                if begin not in dictionary["begin"]:
                    response_text = "给我整不会了"
                    session.clear()
                else:
                    response_word = random.choice(dictionary["begin"][begin])
                    session["word"] = response_word

    if response_word is not None:
        response_text = response_word["word"]
        response_quote = response_word["explanation"]

    if response_text is not None:
        body: Any = {
            "channel": channel,
            "text": response_text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": response_text,
                    },
                },
            ],
        }
        if response_quote is not None:
            body["blocks"].append({"type": "context", "elements": [{"type": "mrkdwn", "text": "> " + response_quote}]})
        await context.api.chat.postMessage(body)
    if response_react is not None:
        body = {"channel": channel, "name": response_react, "timestamp": event.ts}
        await context.api.reactions.add(body)
