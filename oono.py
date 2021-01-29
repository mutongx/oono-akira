#!/usr/bin/env python3

import asyncio
import sys
import time
import json
import aiohttp
import websockets
from datetime import date, datetime
from calendar import monthrange, weekday
from pymongo.client_session import ClientSession
from motor.motor_asyncio import AsyncIOMotorClient


from typing import Optional


def log(s: str):
    print(f"[{datetime.now().isoformat()}] {s}", file=sys.stderr)


class OonoApp:

    def __init__(self, slack_config: dict, mongo_config: Optional[dict]):
        self._app_token = slack_config["token"]["app"]
        self._workspace_token = slack_config["token"]["workspace"]
        self._app_session = None
        self._bot_session = None

        self._db_client = AsyncIOMotorClient(mongo_config["url"]) if mongo_config is not None else None
        self._db_name = mongo_config["db"] if mongo_config is not None else None
        self._db_session = None
        self._db = None

    async def __aenter__(self):
        self._app_session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._app_token}"}
        )
        self._bot_session = aiohttp.ClientSession()
        if self._db_client is not None:
            self._db_session = await self._db_client.start_session()
            self._db = self._db_client[self._db_name]
        return self

    async def __aexit__(self, *err):
        coroutines = [
            self._app_session.close(),
            self._bot_session.close(),
            self._db_session.end_session() if self._db_session is not None else None
        ]
        await asyncio.gather(*filter(lambda cr: cr is not None, coroutines))

    async def run(self):
        while True:

            try:

                log("Trying to establish connection")
                conn_resp = await self._app_session.post("https://slack.com/api/apps.connections.open")
                if not conn_resp.ok:
                    log("Failed to request connections.open, retrying...")
                    time.sleep(5)
                    continue

                conn_url = await conn_resp.json()
                if not conn_url["ok"]:
                    log(f"connections.open() returned error: {conn_url['error']}, retrying...")
                    time.sleep(5)
                    continue

                async with websockets.connect(conn_url["url"], close_timeout=0) as conn:
                    async for message in conn:
                        message = json.loads(message)
                        asyncio.create_task(self.record_message(message))
                        asyncio.create_task(self.handle_message(conn, message))

                log(f"Disconnected.")

            except Exception:

                import traceback
                traceback.print_exc()

    async def record_message(self, message: dict):
        if self._db is None:
            return
        if "envelope_id" in message:
            await self._db.ws_payload.insert_one({
                "_id": message["envelope_id"],
                "timestamp": time.time(),
                **message
            }, session=self._db_session)

    async def handle_message(self, conn: websockets.WebSocketClientProtocol, message: dict):

        ack_payload = None

        if message["type"] == "hello":
            log(f"WebSocket connection established, appid = {message['connection_info']['app_id']}")
        elif message["type"] == "disconnect":
            log(f"Received disconnect request, reason: {message['reason']}")
            await conn.close()
        elif message["type"] == "events_api":
            retry_attempt = message["retry_attempt"]
            if retry_attempt == 0:
                team = message["payload"]["team_id"]
                event = message["payload"]["event"]
                if event["type"] == "app_mention":
                    ack_payload = self.handle_mention(team, event)
                else:
                    log(f"Unhandled event: {event}")
            else:
                log(f"Retried event: {message}")
        else:
            log(f"Unhandled message: {message}")

        if "envelope_id" in message:
            ack = json.dumps({
                "envelope_id": message["envelope_id"],
                "payload": await ack_payload if ack_payload is not None else None
            })
            asyncio.create_task(conn.send(ack))
            await conn.send(ack)

    async def handle_mention(self, team, event):

        team_info = self._workspace_token.get(team)
        if team_info is None:
            log(f"Error: Team ID {team} is not found in config")
            return
        log(f"Received mention from team {team_info['name']}")

        message = {
            "channel": event["channel"],
            "text": self.get_message()
        }

        if "thread_ts" in event:
            message["thread_ts"] = event["thread_ts"]

        resp = await self._bot_session.post(
            "https://slack.com/api/chat.postMessage", json=message,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {team_info['token']}"
            })

        if not resp.ok:
            log(f"Error sending message: {resp.status_code}")
            return

        j = await resp.json()
        if not j["ok"]:
            log(f"chat.postMessage returned error: {j['error']}")
            return

    def get_message(self):

        now = datetime.now()

        weekday = now.weekday()
        weekday_cn = "一二三四五六日"

        # 0-3 深夜
        if now.hour <= 3:
            greeting = "深夜好"
        # 4-6 凌晨
        elif now.hour <= 6:
            greeting = "凌晨好"
        # 7-10 早上
        elif now.hour <= 10:
            greeting = "早上好"
        # 11-14 中午
        elif now.hour <= 14:
            greeting = "中午好"
        # 15-18 下午
        elif now.hour <= 18:
            greeting = "下午好"
        # 19-22 晚上
        elif now.hour <= 22:
            greeting = "晚上好"
        # 23-24 深夜
        else:
            greeting = "深夜好"

        minute_perc = (now.second * 1e6 + now.microsecond) / 60 / 1e6
        hour_perc = (now.minute * 60 + now.second) / 60 / 60
        day_perc = (now.hour * 60 * 60 + now.minute * 60 + now.second) / 60 / 60 / 24
        week_perc = (weekday * 24 * 60 + now.hour * 60 + now.minute) / 60 / 24 / 7
        _, days_month = monthrange(now.year, now.month)
        month_perc = (now.day * 60 * 60 + now.hour * 60 + now.minute) / 60 / 60 / days_month
        days_year = (datetime(now.year + 1, 1, 1) - datetime(now.year, 1, 1)).days
        year_perc = ((now - datetime(now.year, 1, 1)).days * 24 + now.hour) / days_year / 24
        days_centry = (datetime(now.year // 100 * 100 + 100, 1, 1) - datetime(now.year // 100 * 100, 1, 1)).days
        centry_perc = ((now - datetime(now.year // 100 * 100, 1, 1)).days) / days_centry
        return f"{greeting}，" + \
            f"现在是 {now.strftime('%Y 年 %m 月 %d 日 %H:%M')}，星期{weekday_cn[weekday]} (CST)\n" + \
            f"\n" + \
            f"这分钟已经过去了 {minute_perc * 100:.1f}%\n" + \
            f"这小时已经过去了 {hour_perc * 100:.1f}%\n" + \
            f"这一天已经过去了 {day_perc * 100:.1f}%\n" + \
            f"这一周已经过去了 {week_perc * 100:.1f}%\n" + \
            f"这个月已经过去了 {month_perc * 100:.1f}%\n" + \
            f"这一年已经过去了 {year_perc * 100:.1f}%\n" + \
            f"这世纪已经过去了 {centry_perc * 100:.1f}%\n" + \
            f"\n" + \
            f"生命不息，摸鱼不止。"


async def amain():
    with open("config.json") as f:
        config = json.load(f)
    async with OonoApp(config["slack"], config["mongo"]) as oono:
        await oono.run()


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        log("Exited.")
        pass
