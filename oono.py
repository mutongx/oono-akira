#!/usr/bin/env python3

import asyncio
import sys
import time
import json
import aiohttp
import websockets
from datetime import date, datetime
from calendar import monthrange, weekday


def log(s: str):
    print(s, file=sys.stderr)


class OonoApp:

    def __init__(self, app_token: str, bot_token: str):
        self._app_token = app_token
        self._bot_token = bot_token
        self._app_session = None
        self._bot_session = None

    async def __aenter__(self):
        self._app_session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._app_token}"}
        )
        self._bot_session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._bot_token}"}
        )
        return self

    async def __aexit__(self, *err):
        await asyncio.gather(
            self._app_session.close(),
            self._bot_session.close()
        )

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

                async with websockets.connect(conn_url["url"]) as conn:
                    async for message in conn:

                        message = json.loads(message)
                        ack_payload = None

                        if message["type"] == "hello":
                            log(f"WebSocket connection established, appid = {message['connection_info']['app_id']}")
                        elif message["type"] == "disconnect":
                            log(f"Received disconnect request, reason: {message['reason']}")
                            break
                        elif message["type"] == "events_api":
                            retry_attempt = message["retry_attempt"]
                            if retry_attempt == 0:
                                event = message["payload"]["event"]
                                if event["type"] == "app_mention":
                                    ack_payload = self.handle_mention(event)
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


                log(f"Disconnected.")

            except Exception:

                import traceback
                traceback.print_exc()

    async def handle_mention(self, event):
        resp = await self._bot_session.post("https://slack.com/api/chat.postMessage", json={
            "channel": event["channel"],
            "text": self.get_message()
        }, headers={
            "Content-Type": "application/json; charset=utf-8"
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
    app_token = config["slack"]["token"]["app"]
    bot_token = config["slack"]["token"]["workspace"]["mai"]
    async with OonoApp(app_token, bot_token) as oono:
        await oono.run()


if __name__ == "__main__":
    asyncio.run(amain())
