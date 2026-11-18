from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .bark import push_scan
from .calendar import load_trading_days, latest_session
from .config import CACHE_DIR, HISTORY_YEARS, PUBLIC_DIR
from .publish import publish
from .tencent import load_or_update_cache
from .universe import load_universe
from .vegas import scan_symbol

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _history_start(end: date) -> date:
    try:
        return end.replace(year=end.year - HISTORY_YEARS)
    except ValueError:
        return end.replace(year=end.year - HISTORY_YEARS, day=28)


def run_scan(force: bool = False) -> int:
    now = datetime.now(SHANGHAI)
    today = now.date()
    days = load_trading_days()
    session = latest_session(days, today)
    if session is None or session != today:
        print("No China A-share trading session today; scan skipped.")
        return 0
    if not force and (now.hour, now.minute) < (15, 35):
        raise RuntimeError("Daily scan is not allowed before 15:35 Asia/Shanghai")

    universe = load_universe()
    start = _history_start(session)
    diagnostics = {
        "source": "Tencent QFQ daily",
        "timeframe": "1D",
        "data_date": session.isoformat(),
        "pool_expected": len(universe),
        "pool_ok": 0,
        "pool_failed": [],
        "status": "running",
    }
    all_signals = []
    for index, stock in enumerate(universe, 1):
        code, name = stock["code"], stock["name"]
        try:
            rows = load_or_update_cache(code, start, session, CACHE_DIR)
            if not rows:
                raise RuntimeError("empty daily history")
            actual_date = rows[-1][0]
            if actual_date != session.isoformat():
                raise RuntimeError(f"stale data: expected {session.isoformat()}, received {actual_date}")
            all_signals.extend(
                signal for signal in scan_symbol(rows, code, name)
                if signal["date"] == session.isoformat()
            )
            diagnostics["pool_ok"] += 1
        except Exception as error:
            diagnostics["pool_failed"].append({"code": code, "name": name, "error": str(error)})
        if index % 25 == 0:
            print(f"Scanned {index}/{len(universe)}")

    diagnostics["signals_count"] = len(all_signals)
    if diagnostics["pool_ok"] != len(universe) or diagnostics["pool_failed"]:
        diagnostics["status"] = "failed"
        diagnostics["error"] = "Incomplete pool scan; existing publication preserved."
        PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
        (PUBLIC_DIR / "ashare-diagnostics.json").write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2), "utf-8"
        )
        raise RuntimeError(diagnostics["error"])

    diagnostics["status"] = "success"
    publish(all_signals, diagnostics, PUBLIC_DIR)
    pushed = push_scan(all_signals, session.isoformat())
    diagnostics["bark_pushed"] = pushed
    publish(all_signals, diagnostics, PUBLIC_DIR)
    print(f"Published {len(all_signals)} signals for {session.isoformat()}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Manual run after market close; does not bypass data validation.")
    args = parser.parse_args()
    try:
        raise SystemExit(run_scan(force=args.force))
    except Exception as exc:
        print(f"A-share scan failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
