from __future__ import annotations

from .config import EMA_PERIODS


def ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("EMA period must be positive")
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    alpha = 2.0 / (period + 1)
    previous = seed
    for index in range(period, len(values)):
        previous = values[index] * alpha + previous * (1 - alpha)
        result[index] = previous
    return result


def add_emas(rows: list[list]) -> list[dict]:
    closes = [float(row[2]) for row in rows]
    series = {period: ema(closes, period) for period in EMA_PERIODS}
    result = []
    for index, row in enumerate(rows):
        item = {
            "date": row[0], "open": float(row[1]), "close": closes[index],
            "high": float(row[3]), "low": float(row[4]),
        }
        for period, values in series.items():
            item[f"ema{period}"] = values[index]
        result.append(item)
    return result


def _overlaps_zone(low: float, high: float, first: float | None, second: float | None) -> bool:
    if first is None or second is None:
        return False
    return low <= max(first, second) and high >= min(first, second)


def scan_symbol(rows: list[list], code: str, name: str) -> list[dict]:
    bars = add_emas(rows)
    observations: list[dict] = []
    signals: list[dict] = []
    for index, bar in enumerate(bars):
        if bar["ema12"] is None:
            continue
        for zone, a, b in (("middle", "ema144", "ema169"), ("red", "ema576", "ema676")):
            if _overlaps_zone(bar["low"], bar["high"], bar[a], bar[b]):
                observations.append({"index": index, "date": bar["date"], "zone": zone})
        for observation in list(observations):
            if index <= observation["index"]:
                continue
            direction = "long" if bar["close"] > bar["ema12"] else "short" if bar["close"] < bar["ema12"] else None
            if direction:
                signals.append({
                    "code": code, "name": name, "date": bar["date"],
                    "zone": observation["zone"], "direction": direction,
                    "close": bar["close"], "ema12": bar["ema12"],
                    "touch_date": observation["date"],
                })
                observations.remove(observation)
                break
    return signals
