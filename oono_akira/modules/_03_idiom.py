import asyncio
import json
import random
import unicodedata
from collections import defaultdict
from typing import Any

import aiohttp
from oono_akira.log import log
from oono_akira.modules import HandlerType, register
from oono_akira.slack import SlackContext

dict_data_url = "https://github.com/pwxcoo/chinese-xinhua/raw/master/data/idiom.json"
dict_data = None


async def get_data():
    global dict_data
    if dict_data is None:
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(dict_data_url) as resp:
                text = await resp.text()
        raw = json.loads(text)
        data: Any = {
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
                    lambda s: unicodedata.normalize("NFKD", s)
                    .encode("ascii", "ignore")
                    .decode(),
                    pinyin,
                )
            )
            item["pinyin_normalized"] = pinyin
            begin = pinyin[0]
            end = pinyin[-1]
            data["begin"][begin].append(item)
            data["end"][end].append(item)
            data["mapping"][item["word"]] = item
            data["list"].append(item)
        dict_data = data
    return dict_data


@register("message")
def handler(context: SlackContext) -> HandlerType:
    text = context["event"].get("text")
    if not text:
        return
    db = context["database"]
    channel = context["event"]["channel"]
    if text == "成语接龙":
        asyncio.create_task(get_data())
        with db.get_session(game="idiom", channel=channel) as session:
            session.data["status"] = "BEGIN"
        return channel, process
    elif len(text) == 4 or text == "不会" or text == "不玩了":
        with db.get_session(game="idiom", channel=channel) as session:
            if session.data.get("status") != "ONGOING":
                return
            return channel, process


async def process(context: SlackContext):
    context["ack"]()
    event = context["event"]
    answer = event["text"]
    channel = event["channel"]
    database = context["database"]
    data = await get_data()
    react = None
    text = None
    meaning = None
    with database.get_session(game="idiom", channel=channel) as session:
        status = session.data.get("status")
        if status == "BEGIN":
            session.data["status"] = "ONGOING"
            word = random.choice(data["list"])
            session.data["word"] = word
            text = word["word"]
            meaning = word["explanation"]
        elif status == "ONGOING":
            if answer == "不玩了":
                text = "祝你身体健康"
                session.data["status"] = "END"
            elif answer == "不会":
                begin = session.data["word"]["pinyin_normalized"][-1]
                if begin not in data["begin"]:
                    text = "草，我也不会"
                    session.data["status"] = "END"
                else:
                    word = random.choice(data["begin"][begin])
                    session.data["word"] = word
                    text = word["word"]
                    meaning = word["explanation"]
            else:
                match = data["mapping"].get(answer)
                if (
                    match is None
                    or match["pinyin_normalized"][0]
                    != session.data["word"]["pinyin_normalized"][-1]
                ):
                    react = "x"
                else:
                    begin = match["pinyin_normalized"][-1]
                    if not data["begin"][begin]:
                        text = "给我整不会了"
                        session.data["status"] = "END"
                    else:
                        word = random.choice(data["begin"][begin])
                        session.data["word"] = word
                        text = word["word"]
                        meaning = word["explanation"]
        else:
            log(f"Wrong session status ({status}) for channel {channel}")
    if text is not None:
        body: Any = {
            "channel": channel,
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                },
            ],
        }
        if meaning is not None:
            body["blocks"].append(
                {"type": "context", "elements": [{"type": "mrkdwn", "text": "> " + meaning}]}
            )
        await context["api"].chat.postMessage(body)
    if react is not None:
        body = {"channel": channel, "name": react, "timestamp": event["ts"]}
        await context["api"].reactions.add(body)
