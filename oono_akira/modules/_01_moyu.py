from calendar import monthrange
from datetime import datetime
from typing import Any

import pytz
from oono_akira.modules import HandlerType, register
from oono_akira.slack import SlackContext

TIMEZONE = pytz.timezone("Asia/Shanghai")


@staticmethod
def datetime_tz(*args: Any, **kwargs: Any):
    return datetime(*args, **kwargs, tzinfo=TIMEZONE)


@staticmethod
def get_message() -> str:
    now = datetime.now(tz=TIMEZONE)

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
    days_year = (datetime_tz(now.year + 1, 1, 1) - datetime_tz(now.year, 1, 1)).days
    year_perc = ((now - datetime_tz(now.year, 1, 1)).days * 24 + now.hour) / days_year / 24
    days_centry = (datetime_tz(now.year // 100 * 100 + 100, 1, 1) - datetime_tz(now.year // 100 * 100, 1, 1)).days
    centry_perc = ((now - datetime_tz(now.year // 100 * 100, 1, 1)).days) / days_centry
    return "\n".join(
        [
            f"{greeting}，现在是 {now.strftime('%Y 年 %m 月 %d 日 %H:%M')}，星期{weekday_cn[weekday]} (CST)",
            f"",
            f"这分钟已经过去了 {minute_perc * 100:.1f}%",
            f"这小时已经过去了 {hour_perc * 100:.1f}%",
            f"这一天已经过去了 {day_perc * 100:.1f}%",
            f"这一周已经过去了 {week_perc * 100:.1f}%",
            f"这个月已经过去了 {month_perc * 100:.1f}%",
            f"这一年已经过去了 {year_perc * 100:.1f}%",
            f"这世纪已经过去了 {centry_perc * 100:.1f}%",
            f"",
            f"生命不息，摸鱼不止。",
        ]
    )


@register("message")
def message_handler(context: SlackContext) -> HandlerType:
    if context.event.bot_id:
        return
    if not context.event.text:
        return
    if context.event.text == f"<@{context.workspace.botId}>":

        async def ignore(context: SlackContext):
            await context.ack()

        return ignore, {}


@register("app_mention")
def app_mention_handler(context: SlackContext) -> HandlerType:
    if context.event.bot_id:
        return
    if not context.event.text:
        return
    if context.event.text == f"<@{context.workspace.botId}>":
        return process, {}


async def process(context: SlackContext):
    await context.ack()
    event = context.event
    body = {
        "channel": event.channel,
        "text": get_message(),
    }
    if event.thread_ts:
        body["thread_ts"] = event.thread_ts
    await context.api.chat.postMessage(body)
