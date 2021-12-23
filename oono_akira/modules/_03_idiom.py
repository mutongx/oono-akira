import random
import json
from typing import Optional
import aiohttp
import asyncio
import unicodedata
from collections import defaultdict
from oono_akira.log import log
from oono_akira.modules.__base__ import ModuleBase
from oono_akira.slack import SlackContext
from oono_akira.db import OonoDatabase


class Idiom(ModuleBase):

    DATA_URL = "https://github.com/pwxcoo/chinese-xinhua/raw/master/data/idiom.json"
    DATA = None

    BYE_TEXT_URL = "https://gist.githubusercontent.com/mutongx/e68ca5f6af54bd9989f11a1b615a8574/raw/sad_huoxing.txt"
    BYE_TEXT = None

    @staticmethod
    async def get_data():
        if Idiom.DATA is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(Idiom.DATA_URL) as resp:
                    text = await resp.text()
            raw = json.loads(text)
            data = {
                "begin": defaultdict(list),
                "end": defaultdict(list),
                "mapping": {},
                "list": []
            }
            for item in raw:
                pinyin = item["pinyin"].split()
                if len(pinyin) != 4:
                    continue
                pinyin = list(map(
                    lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode(),
                    pinyin))
                item["pinyin_normalized"] = pinyin
                begin = pinyin[0]
                end = pinyin[-1]
                data["begin"][begin].append(item)
                data["end"][end].append(item)
                data["mapping"][item["word"]] = item
                data["list"].append(item)
            Idiom.DATA = data
        return Idiom.DATA

    @staticmethod
    async def get_bye_text():
        if Idiom.BYE_TEXT is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(Idiom.BYE_TEXT_URL) as resp:
                    text = await resp.text()
            Idiom.BYE_TEXT = text.strip().split("\n")
        return random.choice(Idiom.BYE_TEXT)

    @staticmethod
    def check_message(context: SlackContext) -> Optional[str]:
        text = context["event"].get("text")
        if not text:
            return
        db = context["database"] # type: OonoDatabase
        channel = context["event"]["channel"]
        if text == "成语接龙":
            asyncio.create_task(Idiom.get_data())
            asyncio.create_task(Idiom.get_bye_text())
            with db.get_session(channel=channel) as session:
                session["status"] = "BEGIN"
            return channel
        elif len(text) == 4 or text == "不会" or text == "不玩了":
            with db.get_session(channel=channel) as session:
                if session.get("status") != "ONGOING":
                    return
                return channel

    async def process(self):
        event = self._slack_context["event"]
        answer = event["text"]
        channel = event["channel"]
        database = self._slack_context["database"]
        data = await self.get_data()
        react = None
        text = None
        meaning = None
        with database.get_session(channel=channel) as session:
            status = session.get("status")
            if status == "BEGIN":
                session["status"] = "ONGOING"
                word = random.choice(data["list"])
                session["word"] = word
                text = word["word"]
                meaning = word["explanation"]
            elif status == "ONGOING":
                if answer == "不玩了":
                    text = await self.get_bye_text()
                    session["status"] = "END"
                elif answer == "不会":
                    begin = session["word"]["pinyin_normalized"][-1]
                    if begin not in data["begin"]:
                        text = "草，我也不会"
                        session["status"] = "END"
                    else:
                        word = random.choice(data["begin"][begin])
                        session["word"] = word
                        text = word["word"]
                        meaning = word["explanation"]
                else:
                    match = data["mapping"].get(answer)
                    if match is None or match["pinyin_normalized"][0] != session["word"]["pinyin_normalized"][-1]:
                        react = "x"
                    else:
                        begin = match["pinyin_normalized"][-1]
                        if not data["begin"][begin]:
                            text = "给我整不会了"
                            session["status"] = "END"
                        else:
                            word = random.choice(data["begin"][begin])
                            session["word"] = word
                            text = word["word"]
                            meaning = word["explanation"]
            else:
                log(f"Wrong session status ({status}) for channel {channel}")
        if text is not None:
            body = {
                "channel": channel,
                "text": text
            }
            resp = await self._slack_api.chat.postMessage(body)
            if meaning is not None:
                meaning_body = {
                    "channel": channel,
                    "text": meaning,
                    "thread_ts": resp["ts"]
                }
                await self._slack_api.chat.postMessage(meaning_body)
        if react is not None:
            body = {
                "channel": channel,
                "name": react,
                "timestamp": event["ts"]
            }
            await self._slack_api.reactions.add(body)

MODULE = Idiom
