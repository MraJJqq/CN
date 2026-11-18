from __future__ import annotations

import csv
from .config import EXPECTED_UNIVERSE_SIZE, UNIVERSE_FILE

FORBIDDEN_NAME_MARKERS = ("ST", "*ST", "退", "退市")


def load_universe(path=UNIVERSE_FILE) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing fixed CN500 list: {path}. Do not generate or rotate constituents dynamically."
        )
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not {"code", "name"}.issubset(rows[0]):
        raise ValueError("CN500 CSV must have code,name columns")
    normalized = []
    seen = set()
    for row in rows:
        code, name = row["code"].strip(), row["name"].strip()
        if len(code) != 6 or not code.isdigit():
            raise ValueError(f"invalid stock code: {code}")
        if code in seen:
            raise ValueError(f"duplicate CN500 code: {code}")
        if not name or any(marker in name.upper() for marker in FORBIDDEN_NAME_MARKERS):
            raise ValueError(f"ST/delisted or invalid stock name: {code} {name}")
        seen.add(code)
        normalized.append({"code": code, "name": name})
    if len(normalized) != EXPECTED_UNIVERSE_SIZE:
        raise ValueError(f"CN500 must contain exactly {EXPECTED_UNIVERSE_SIZE} rows; got {len(normalized)}")
    return normalized
