from datetime import datetime, timedelta
from typing import Any

import pytz
from oono_akira.modules import Handler, HandlerConstructorOption, register
from oono_akira.slack.context import SlackContext

TIMEZONE = pytz.timezone("Asia/Shanghai")
DAYS_IN_MONTH = [-1, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def datetime_tz(*args: Any, **kwargs: Any):
    return TIMEZONE.localize(datetime(*args, **kwargs))


def get_message() -> str:
    now = datetime.now(tz=TIMEZONE)

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

    weekday = now.weekday()
    year_100 = now.year // 100 * 100

    minute = datetime_tz(now.year, now.month, now.day, now.hour, now.minute), timedelta(minutes=1)
    hour = datetime_tz(now.year, now.month, now.day, now.hour), timedelta(hours=1)
    day = datetime_tz(now.year, now.month, now.day), timedelta(days=1)
    week = datetime_tz(now.year, now.month, now.day) - timedelta(days=weekday), timedelta(days=7)
    month = datetime_tz(now.year, now.month, 1, 0, 0, 0), timedelta(days=DAYS_IN_MONTH[now.month])
    year = datetime_tz(now.year, 1, 1), datetime_tz(now.year + 1, 1, 1) - datetime_tz(now.year, 1, 1)
    centry = datetime_tz(year_100, 1, 1, 0), datetime_tz(year_100 + 100, 1, 1, 0) - datetime_tz(year_100, 1, 1, 0)

    def get_percentage(d: tuple[datetime, timedelta]) -> str:
        nonlocal now
        return f"{int((now - d[0]).total_seconds() / d[1].total_seconds() * 1000) / 10:.1f}"

    return "\n".join(
        [
            f"{greeting}，现在是 {now.strftime('%Y 年 %m 月 %d 日 %H:%M')}，星期{WEEKDAY_CN[weekday]} (CST)",
            f"",
            f"这分钟已经过去了 {get_percentage(minute)}%",
            f"这小时已经过去了 {get_percentage(hour)}%",
            f"这一天已经过去了 {get_percentage(day)}%",
            f"这一周已经过去了 {get_percentage(week)}%",
            f"这个月已经过去了 {get_percentage(month)}%",
            f"这一年已经过去了 {get_percentage(year)}%",
            f"这世纪已经过去了 {get_percentage(centry)}%",
            f"",
            f"生命不息，摸鱼不止。",
        ]
    )


@register("message")
def message_handler(context: SlackContext, option: HandlerConstructorOption) -> Handler:
    if not option["has_access"]:
        return
    event = context.must_event()
    if event.bot_id:
        return
    if not event.text:
        return
    if event.text == f"<@{context.workspace.botId}>":

        async def ignore(context: SlackContext):
            await context.ack()

        return ignore, {}


@register("app_mention")
def app_mention_handler(context: SlackContext, option: HandlerConstructorOption) -> Handler:
    if not option["has_access"]:
        return
    event = context.must_event()
    if event.bot_id:
        return
    if not event.text:
        return
    if event.text == f"<@{context.workspace.botId}>":
        return process, {}


async def process(context: SlackContext):
    await context.ack()
    await context.api.chat.postMessage({**context.reply_args(), "text": get_message()})
