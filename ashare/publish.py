from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), "utf-8")
    os.replace(temp, path)


def publish(signals: list[dict], diagnostics: dict, public_dir: Path) -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    atomic_json(public_dir / "ashare-signals.json", {
        "source": "CN A-share",
        "timeframe": "1D",
        "data_date": diagnostics["data_date"],
        "generated_at": stamp,
        "signals": signals,
    })
    atomic_json(public_dir / "ashare-diagnostics.json", diagnostics)
