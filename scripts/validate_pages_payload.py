#!/usr/bin/env python3
"""Validate the complete static payload before Bark notifications or Pages deployment."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .trading_calendar import china_today, is_a_share_trading_day, previous_a_share_trading_day
except ImportError:
    from trading_calendar import china_today, is_a_share_trading_day, previous_a_share_trading_day


REQUIRED_FILES = (
    "cards.json",
    "summary.json",
    "universe.json",
    "signals.json",
    "signals.previous.json",
    "trading-calendar.json",
)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Missing or invalid JSON payload: {path.name}") from error


def validate_payload(data: Path, expected_market_date: str | None = None) -> dict:
    missing = [name for name in REQUIRED_FILES if not (data / name).is_file()]
    if missing:
        raise ValueError(f"Missing Pages data files: {missing}")

    cards = _load(data / "cards.json")
    summary = _load(data / "summary.json")
    universe = _load(data / "universe.json")
    signals = _load(data / "signals.json")
    previous_signals = _load(data / "signals.previous.json")
    trading_calendar = _load(data / "trading-calendar.json")

    if not isinstance(cards, list) or len(cards) != 500:
        raise ValueError("CN500 cards payload must contain exactly 500 rows")
    card_symbols = [row.get("symbol") for row in cards if isinstance(row, dict)]
    if len(card_symbols) != 500 or len(set(card_symbols)) != 500 or any(not isinstance(symbol, str) or not symbol for symbol in card_symbols):
        raise ValueError("CN500 cards payload must contain exactly 500 unique symbols")
    for row in cards:
        status = row.get("status", "ready")
        latest = row.get("latest_close")
        previous = row.get("previous_close")
        if status not in {"ready", "unavailable", "error"}:
            raise ValueError(f"CN500 card has an unsupported status: {status!r}")
        if status == "ready" and (not isinstance(latest, (int, float)) or isinstance(latest, bool) or latest <= 0):
            raise ValueError(f"Ready CN500 card is missing a positive latest_close: {row['symbol']}")
        if latest is not None and (not isinstance(latest, (int, float)) or isinstance(latest, bool) or latest <= 0):
            raise ValueError(f"CN500 card has an invalid latest_close: {row['symbol']}")
        if previous is not None and (not isinstance(previous, (int, float)) or isinstance(previous, bool) or previous <= 0):
            raise ValueError(f"CN500 card has an invalid previous_close: {row['symbol']}")
    if not isinstance(universe, list) or not isinstance(signals, list) or not isinstance(previous_signals, list):
        raise ValueError("Universe and signal payloads must be arrays")
    if summary.get("universe_size") != 500 or summary.get("eligible_count") != len(universe):
        raise ValueError("CN500 summary and eligible universe counts disagree")
    if summary.get("fetch_error_count") != 0:
        raise ValueError("Refusing to publish a snapshot with Tencent fetch errors")
    if summary.get("web_ema_policy") != "EMA12/144/169/576/676 calculated from the full available 10-year Tencent history and aligned to displayed bars":
        raise ValueError("Summary does not declare full-history EMA chart data")

    # The market date is the newest session present in the eligible universe.
    # Individual eligible stocks may legitimately have an older last_date
    # (e.g. suspension); their own chart must still match that stock's date.
    market_date = summary.get("market_date")
    newest_date = max((str(row.get("last_date") or "") for row in universe), default="")
    if not market_date or market_date != newest_date:
        raise ValueError("Summary market date must equal the newest eligible-stock date")
    if not isinstance(trading_calendar, dict) or not isinstance(trading_calendar.get("trading_days"), list):
        raise ValueError("Official trading calendar payload is invalid")
    if market_date not in trading_calendar["trading_days"]:
        raise ValueError("Summary market_date is missing from the official trading calendar")
    if expected_market_date is not None and market_date != expected_market_date:
        raise ValueError(
            "Refusing stale market payload: "
            f"expected latest completed SSE session {expected_market_date}, got {market_date}"
        )
    previous_market_date = summary.get("previous_market_date")
    if not previous_market_date:
        raise ValueError("Summary is missing previous_market_date")
    expected_previous = previous_a_share_trading_day(datetime.strptime(market_date, "%Y-%m-%d").date()).isoformat()
    if previous_market_date != expected_previous:
        raise ValueError("Summary previous_market_date does not match the official prior SSE session")

    symbols = [row.get("symbol") for row in universe if isinstance(row, dict)]
    if len(symbols) != len(universe) or len(set(symbols)) != len(symbols) or any(not isinstance(symbol, str) or not symbol for symbol in symbols):
        raise ValueError("Eligible universe contains missing or duplicate symbols")
    symbol_set = set(symbols)

    # Every ready card must have a matching chart/universe row; unavailable
    # cards are permitted for legitimate exclusions such as ST or suspension.
    cards_by_symbol = {row["symbol"]: row for row in cards}
    ready_symbols = {row["symbol"] for row in cards if row.get("status", "ready") == "ready"}
    if ready_symbols != symbol_set:
        missing_cards = sorted(symbol_set - ready_symbols)[:10]
        orphan_cards = sorted(ready_symbols - symbol_set)[:10]
        raise ValueError(
            "Ready CN500 cards and eligible universe disagree: "
            f"missing_ready={missing_cards}, orphan_ready={orphan_cards}"
        )
    for stock in universe:
        card = cards_by_symbol[stock["symbol"]]
        if card.get("last_date") != stock.get("last_date"):
            raise ValueError(f"CN500 card date does not match eligible data: {stock['symbol']}")
        if card.get("valid_bars") != stock.get("valid_bars"):
            raise ValueError(f"CN500 card history count does not match eligible data: {stock['symbol']}")
    if any(not isinstance(row, dict) or row.get("symbol") not in symbol_set or row.get("confirmation_date") != market_date for row in signals):
        raise ValueError("Signal payload contains an unknown symbol or non-current session")
    if any(
        not isinstance(row, dict)
        or row.get("symbol") not in symbol_set
        or row.get("confirmation_date") != previous_market_date
        for row in previous_signals
    ):
        raise ValueError("Previous signal payload contains an unknown symbol or wrong previous session")
    if len(signals) != summary.get("today_signal_count") or len(previous_signals) != summary.get("previous_signal_count"):
        raise ValueError("Summary and current/previous signal counts disagree")

    charts = data / "charts"
    chart_files = list(charts.glob("*.json.gz")) if charts.is_dir() else []
    if len(chart_files) != len(universe):
        raise ValueError(f"Expected {len(universe)} compressed charts, found {len(chart_files)}")

    for stock in universe:
        path = charts / f'{stock["symbol"]}.json.gz'
        if not path.is_file():
            raise ValueError(f"Missing compressed chart: {path.name}")
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                chart = json.load(handle)
        except (OSError, EOFError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid compressed chart: {path.name}") from error
        bars = chart.get("bars")
        if chart.get("symbol") != stock["symbol"] or chart.get("last_date") != stock.get("last_date") or not isinstance(bars, list) or not bars:
            raise ValueError(f"Invalid or date-mismatched compressed chart payload: {path.name}")
        if chart.get("ema_schema") != 2 or chart.get("ema_periods") != [12, 144, 169, 576, 676] or chart.get("ema_source") != "full-history-per-bar":
            raise ValueError(f"Missing full-history EMA series metadata: {path.name}")
        if chart.get("valid_bars") != stock.get("valid_bars"):
            raise ValueError(f"Chart history count does not match eligible data: {path.name}")
        if chart.get("history_complete") is not (len(bars) == chart.get("valid_bars")):
            raise ValueError(f"Chart history completeness flag is inconsistent: {path.name}")
        dates = []
        for bar in bars:
            if not isinstance(bar, list) or len(bar) != 10 or not isinstance(bar[0], str):
                raise ValueError(f"Invalid chart bar structure: {path.name}")
            try:
                parsed_date = datetime.strptime(bar[0], "%Y-%m-%d").date()
            except ValueError as error:
                raise ValueError(f"Invalid chart bar date: {path.name}") from error
            dates.append(parsed_date)
            prices = bar[1:5]
            if any(not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0 for value in prices):
                raise ValueError(f"Invalid chart OHLC values: {path.name}")
            if prices[1] < max(prices[0], prices[3]) or prices[2] > min(prices[0], prices[3]) or prices[1] < prices[2]:
                raise ValueError(f"Inconsistent chart OHLC range: {path.name}")
        if dates != sorted(set(dates)) or dates[-1].isoformat() != chart.get("last_date"):
            raise ValueError(f"Chart bars are duplicated, unordered, or end on the wrong date: {path.name}")
        for index in range(5):
            values = [bar[5 + index] for bar in bars]
            if any(value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0) for value in values):
                raise ValueError(f"Invalid full-history EMA values: {path.name}")

    return {
        "cards": len(cards),
        "eligible": len(universe),
        "signals": len(signals),
        "market_date": market_date,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-previous-snapshot",
        action="store_true",
        help="Allow an older market date for frontend-only publication while retaining every integrity check.",
    )
    parser.add_argument("--data-dir", type=Path, default=root / "site" / "data")
    args = parser.parse_args()
    expected = None
    if not args.allow_previous_snapshot:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        run_date = china_today()
        expected_session = (
            run_date
            if is_a_share_trading_day(run_date)
            and now.time().replace(tzinfo=None) >= dt_time(15, 30)
            else previous_a_share_trading_day(run_date)
        )
        expected = expected_session.isoformat()
    result = validate_payload(args.data_dir, expected_market_date=expected)
    print(
        "Pages payload verified: "
        f'{result["cards"]} CN500 cards, {result["eligible"]} eligible charts, '
        f'{result["signals"]} current-session signals ({result["market_date"]}).'
    )


if __name__ == "__main__":
    main()
