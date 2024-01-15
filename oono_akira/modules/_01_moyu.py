import aiohttp
import asyncio
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from oono_akira.modules import Handler, HandlerConstructorOption, register
from oono_akira.slack.context import SlackContext

TIMEZONE = ZoneInfo("Asia/Shanghai")
DAYS_IN_MONTH = [-1, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]
CHINESE_CALENDAR_URL = "https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T{year}c.txt"
CHINESE_CALENDAR_DATA: dict[int, str] = {}
CHINESE_CALENDAR_MAPPING: dict[tuple[int, int, int], tuple[str, str, str, str | None]] = {}

RE_TITLE = re.compile(r"\d{4}\((\S\S) - 肖\S\)年公曆與農曆日期對照表")
RE_DATE = re.compile(r"^(\d+)年(\d+)月(\d+)日\s+(\S+)\s+星期\S\s+(?:(\S+)\s+)?$")


async def get_chinese_calendar_data(year: int):
    async def get_or_fetch(year: int):
        if year not in CHINESE_CALENDAR_DATA:
            async with aiohttp.ClientSession() as session:
                async with session.get(CHINESE_CALENDAR_URL.format(year=year)) as resp:
                    resp.raise_for_status()
                    data = await resp.text("big5")
            CHINESE_CALENDAR_DATA[year] = data
        return CHINESE_CALENDAR_DATA[year]

    return await asyncio.gather(get_or_fetch(year - 1), get_or_fetch(year))


async def get_chinese_date(now: datetime):
    now_date = (now.year, now.month, now.day)
    if now_date not in CHINESE_CALENDAR_MAPPING:
        last_data, this_data = await get_chinese_calendar_data(now.year)
        last_lines, this_lines = last_data.split("\r\n"), this_data.split("\r\n")
        last_name_match, this_name_match = RE_TITLE.fullmatch(last_lines[0]), RE_TITLE.fullmatch(this_lines[0])
        if last_name_match is None or this_name_match is None:
            raise RuntimeError("failed to get year name")
        last_year, this_year = last_name_match.group(1), this_name_match.group(1)
        current_year = last_year
        current_month = None
        for line in last_lines[-2:2:-1]:
            date_match = RE_DATE.fullmatch(line)
            if date_match is None:
                raise RuntimeError(f"failed to parse date line: {line}")
            date = date_match.group(4)
            if date[-1] == "月":
                current_month = date
                break
        else:
            raise RuntimeError(f"failed to find month of last year")
        for line in this_lines[3:-1]:
            date_match = RE_DATE.fullmatch(line)
            if date_match is None:
                raise RuntimeError(f"failed to parse date line: {line}")
            year_s, month_s, day_s, current_day, day_term = date_match.groups()
            date = int(year_s), int(month_s), int(day_s)
            if current_day == "正月":
                current_year = this_year
            if current_day[-1] == "月":
                current_month = current_day
                current_day = "初一"
            CHINESE_CALENDAR_MAPPING[date] = (current_year, current_month, current_day, day_term)
    return CHINESE_CALENDAR_MAPPING[now_date]


def datetime_tz(*args: Any, **kwargs: Any):
    return datetime(*args, **kwargs, tzinfo=TIMEZONE)


async def get_message() -> str:
    now = datetime.now(tz=TIMEZONE)

    cn_date = await get_chinese_date(now)

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
            f"{greeting}。现在是北京时间 {now.strftime('%Y 年 %m 月 %d 日 %H:%M')}，星期{WEEKDAY_CN[weekday]}。",
            f"",
            f"今天是农历{cn_date[0]}年{cn_date[1]}{cn_date[2]}{f'，{cn_date[3]}' if cn_date[3] else ''}。",
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
    await context.api.chat.postMessage({**context.reply_args(), "text": await get_message()})
