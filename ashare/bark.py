from __future__ import annotations

import os
import urllib.parse
import urllib.request


def push_scan(signals: list[dict], data_date: str) -> bool:
    key = os.environ.get("BARK_KEY", "").strip()
    if not key:
        return False
    title = f"A股 Vegas 信号 · {data_date}"
    if not signals:
        body = "本次扫描无新增确认信号"
    else:
        body = "\n".join(
            f'{row["code"]} {row["name"]} {row["direction"]} {row["zone"]}'
            for row in signals
        )
    url = "https://api.day.app/" + urllib.parse.quote(key, safe="") + "/" + urllib.parse.quote(title, safe="") + "/" + urllib.parse.quote(body, safe="")
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "CN-Ashare/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Bark HTTP {response.status}")
    return True
