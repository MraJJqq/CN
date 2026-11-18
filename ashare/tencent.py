from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def market_code(code: str) -> str:
    code = code.strip().lower()
    if code.startswith(("sh", "sz")):
        return code
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"invalid A-share code: {code}")
    if code.startswith("6"):
        return "sh" + code
    if code.startswith(("0", "3")):
        return "sz" + code
    raise ValueError(f"unsupported non-CN500 exchange code: {code}")


def _fetch_segment(code: str, start: date, end: date) -> list[list]:
    symbol = market_code(code)
    params = urllib.parse.urlencode({
        "param": f"{symbol},day,{start.isoformat()},{end.isoformat()},640,qfq",
        "_": str(int(time.time() * 1000)),
    })
    request = urllib.request.Request(
        f"{BASE_URL}?{params}",
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    node = payload.get("data", {}).get(symbol, {})
    rows = node.get("qfqday")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"Tencent QFQ daily data unavailable for {symbol}")
    return rows


def fetch_daily_qfq(code: str, start: date, end: date) -> list[list]:
    if start > end:
        raise ValueError("start must not be after end")
    rows_by_date: dict[str, list] = {}
    cursor = start
    while cursor <= end:
        segment_end = min(cursor + timedelta(days=729), end)
        for row in _fetch_segment(code, cursor, segment_end):
            if isinstance(row, list) and row and isinstance(row[0], str):
                rows_by_date[row[0]] = row
        cursor = segment_end + timedelta(days=1)
        time.sleep(0.15)
    return [rows_by_date[key] for key in sorted(rows_by_date)]


def load_or_update_cache(code: str, start: date, end: date, cache_dir: Path) -> list[list]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{market_code(code)}-qfq-day.json"
    cached: dict[str, list] = {}
    if path.exists():
        try:
            for row in json.loads(path.read_text("utf-8")):
                cached[row[0]] = row
        except (ValueError, TypeError, IndexError):
            cached = {}
    missing_start = start
    if cached:
        last = max(cached)
        if last >= end.isoformat():
            return [cached[k] for k in sorted(cached) if start.isoformat() <= k <= end.isoformat()]
        missing_start = max(start, date.fromisoformat(last) + timedelta(days=1))
    if missing_start <= end:
        for row in fetch_daily_qfq(code, missing_start, end):
            cached[row[0]] = row
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps([cached[k] for k in sorted(cached)], ensure_ascii=False), "utf-8")
    temp.replace(path)
    return [cached[k] for k in sorted(cached) if start.isoformat() <= k <= end.isoformat()]
