from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .trading_calendar import is_a_share_trading_day
except ImportError:
    from trading_calendar import is_a_share_trading_day


BARK_LINE_WIDTH = 32


def bark_marker_path(market_date: str, directory: str | Path | None = None) -> Path:
    root = Path(directory or os.environ.get("BARK_DEDUPE_DIR", ".cache/cn500-tencent-qfq"))
    return root / f"bark-pushed-{market_date}.json"


def notification_already_sent(market_date: str, directory: str | Path | None = None) -> bool:
    marker = bark_marker_path(market_date, directory)
    try:
        saved = json.loads(marker.read_text(encoding="utf-8"))
        return saved.get("market_date") == market_date and saved.get("status") == "sent"
    except (OSError, ValueError, AttributeError):
        return False


def record_notification_sent(market_date: str, names_count: int, directory: str | Path | None = None) -> Path:
    marker = bark_marker_path(market_date, directory)
    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_suffix(marker.suffix + ".tmp")
    temporary.write_text(json.dumps({"market_date": market_date, "status": "sent", "names_count": names_count, "sent_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()}, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, marker)
    return marker


def format_bark_body(names: list[str], line_width: int = BARK_LINE_WIDTH) -> str:
    """Pack complete ▰ name ▰ units left-to-right and wrap at the fixed width."""
    lines: list[str] = []
    current = ""
    for name in names:
        unit = f"▰ {name} ▰"
        candidate = f"{current} {unit}" if current else unit
        if current and len(candidate) > line_width:
            lines.append(current)
            current = unit
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines) if lines else "▰ No change ▰"


def main() -> int:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    today = now.date()
    if not is_a_share_trading_day(today):
        print(f"{today.isoformat()} is not an A-share trading day; Bark push skipped.")
        return 0
    if now.time().replace(tzinfo=None) < dt_time(15, 30):
        print("A-share market has not closed; Bark push skipped.")
        return 0

    summary = json.loads(Path("site/data/summary.json").read_text(encoding="utf-8"))
    expected_market_date = today.isoformat()
    if summary.get("market_date") != expected_market_date:
        raise RuntimeError(
            "Refusing stale CN Bark payload: "
            f"expected market_date={expected_market_date}, "
            f"got {summary.get('market_date')!r}"
        )

    key = os.environ.get("BARK_KEY", "").strip()
    if not key:
        print("BARK_KEY is not configured; Bark push skipped.")
        return 0

    if notification_already_sent(expected_market_date):
        print(f"CN Bark notification already sent for {expected_market_date}; duplicate push skipped.")
        return 0

    rows = json.loads(Path("site/data/signals.json").read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or row.get("confirmation_date") != expected_market_date
        for row in rows
    ):
        raise RuntimeError("Refusing CN Bark push: signal rows do not all match today's completed market session")
    names = []
    seen = set()
    for row in rows:
        name = str(row.get("name") or "").strip()
        if name and name not in seen:
            names.append(name)
            seen.add(name)

    body = format_bark_body(names)
    server = os.environ.get("BARK_SERVER", "").strip().rstrip("/") or "https://api.day.app"
    payload = json.dumps(
        {"device_key": key, "body": body, "level": "active"},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{server}/push",
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "CN-CN500/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        response_body = response.read().decode("utf-8", "replace")
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Bark push failed: HTTP {response.status}")
    result = json.loads(response_body)
    if result.get("code") != 200:
        raise RuntimeError(f"Bark rejected notification: {response_body[:300]}")
    marker = record_notification_sent(expected_market_date, len(names))
    print(f"Bark push sent: {len(names)} stock names; daily dedupe marker={marker}; response={response_body[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
