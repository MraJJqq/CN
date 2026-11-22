from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, time as dt_time
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

CHINA_TZ = ZoneInfo("Asia/Shanghai")
SSE_CALENDAR_URL = "https://www.sse.com.cn/disclosure/dealinstruc/closed/"
REQUEST_TIMEOUT_SECONDS = 20


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self._ignored += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data):
        if not self._ignored and data.strip():
            self.parts.append(data.strip())


def china_today() -> date:
    return datetime.now(CHINA_TZ).date()


def latest_completed_session(now: datetime | None = None) -> date:
    local_now = (now or datetime.now(CHINA_TZ)).astimezone(CHINA_TZ)
    day = local_now.date()
    if is_a_share_trading_day(day) and local_now.time().replace(tzinfo=None) >= dt_time(15, 30):
        return day
    return previous_a_share_trading_day(day)


def _fetch_exchange_calendar_page()
    response = requests.get(
        SSE_CALENDAR_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; VEGAS-CN/1.0)",
            "Referer": "https://www.sse.com.cn/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    parser = _VisibleText()
    parser.feed(response.text)
    return re.sub(r"\s+", " ", " ".join(parser.parts))


def _year_section(text: str, year: int) -> str:
    heading = re.search(rf"{year}\s*年\s*休市安排", text)
    if not heading:
        raise RuntimeError(f"SSE official trading calendar does not publish {year}")
    tail = text[heading.end():]
    next_heading = re.search(r"(?:\d{4}\s*年\s*休市安排|相关公告)", tail)
    return tail[:next_heading.start()] if next_heading else tail


@lru_cache(maxsize=4)
def exchange_closed_days(year: int) -> frozenset[date]:
    text = _fetch_exchange_calendar_page()
    section = _year_section(text, year)
    closed: set[date] = set()

    range_pattern = re.compile(
        r"(\d{1,2})月(\d{1,2})日\s*(?:（星期[一二三四五六日天]）)?\s*至\s*"
        r"(\d{1,2})月(\d{1,2})日\s*(?:（星期[一二三四五六日天]）)?\s*休市"
    )
    single_pattern = re.compile(
        r"(\d{1,2})月(\d{1,2})日\s*(?:（星期[一二三四五六日天]）)?\s*"
        r"(?:为)?\s*(?:周末)?休市"
    )

    for match in range_pattern.finditer(section):
        start_month, start_day, end_month, end_day = map(int, match.groups())
        start = date(year, start_month, start_day)
        end = date(year, end_month, end_day)
        if end < start:
            raise RuntimeError(f"Invalid SSE holiday range for {year}: {match.group(0)}")
        day = start
        while day <= end:
            closed.add(day)
            day += timedelta(days=1)

    for match in single_pattern.finditer(section):
        month, day = map(int, match.groups())
        closed.add(date(year, month, day))

    if not closed:
        raise RuntimeError(f"Could not parse official SSE holiday closures for {year}")
    return frozenset(closed)


def is_a_share_trading_day(day: date) -> bool:
    # Both mainland stock exchanges close on weekends, including make-up work Saturdays.
    if day.weekday() >= 5:
        return False
    # Do not infer exchange sessions from generic public-holiday/workday calendars.
    # If the exchange has not published the requested year, fail closed.
    return day not in exchange_closed_days(day.year)


def previous_a_share_trading_day(day: date) -> date:
    candidate = day - timedelta(days=1)
    while not is_a_share_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def upcoming_trading_days(start: date, count: int = 40) -> list[str]:
    days = []
    candidate = start
    while len(days) < count:
        try:
            if is_a_share_trading_day(candidate):
                days.append(candidate.isoformat())
        except Exception:
            # The next year's official exchange schedule may not have been published yet.
            break
        candidate += timedelta(days=1)
    return days


def build_status(day: date) -> dict:
    trading = is_a_share_trading_day(day)
    return {
        "date": day.isoformat(),
        "timezone": "Asia/Shanghai",
        "is_trading_day": trading,
        "trading_days": upcoming_trading_days(day),
        "calendar_source": "Shanghai Stock Exchange official annual holiday schedule",
        "calendar_url": SSE_CALENDAR_URL,
        "checked_at": datetime.now(CHINA_TZ).isoformat(),
        "policy": "No scan or Bark push on exchange-published closure days or weekends; fail closed when the exchange has not published the year.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=china_today().isoformat())
    parser.add_argument(
        "--latest-completed-session",
        action="store_true",
        help="Resolve the most recent completed SSE session, including when a scheduled run starts after midnight.",
    )
    parser.add_argument("--write", default="site/data/trading-calendar.json")
    parser.add_argument("--github-output", default="")
    args = parser.parse_args()

    day = latest_completed_session() if args.latest_completed_session else date.fromisoformat(args.date)
    status = build_status(day)

    output = Path(args.write)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            handle.write(f"is-trading-day={'true' if status['is_trading_day'] else 'false'}\n")
            handle.write(f"trade-date={day.isoformat()}\n")

    print(json.dumps(status, ensure_ascii=False), flush=True)
    if not status["is_trading_day"]:
        print(f"{day.isoformat()} is not an A-share trading day; scan and notification will be skipped.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Official exchange calendar unavailable or unsupported; fail-closed: {exc}", file=sys.stderr, flush=True)
        raise
