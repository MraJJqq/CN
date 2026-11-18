from __future__ import annotations

import json
from datetime import date
from .config import DATA_DIR


def load_trading_days(path=DATA_DIR / "trading-days.json") -> list[date]:
    if not path.exists():
        raise FileNotFoundError("Missing official China trading calendar: ashare/data/trading-days.json")
    payload = json.loads(path.read_text("utf-8"))
    values = payload.get("trading_days")
    if not isinstance(values, list) or not values:
        raise ValueError("Trading calendar must contain a non-empty trading_days array")
    days = [date.fromisoformat(value) for value in values]
    if days != sorted(set(days)):
        raise ValueError("Trading calendar contains duplicates or is not sorted")
    return days


def latest_session(days: list[date], today: date) -> date | None:
    eligible = [day for day in days if day <= today]
    return eligible[-1] if eligible else None
