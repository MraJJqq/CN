from __future__ import annotations
import json,os,urllib.request
from datetime import datetime,time
from pathlib import Path
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Shanghai")
def main():
 now=datetime.now(TZ);day=now.date().isoformat()
 if now.time().replace(tzinfo=None)<time(15,30):raise RuntimeError("CN Bark is allowed only after the 15:30 close")
 summary=json.loads(Path("site/data/summary.json").read_text(encoding="utf-8"))
 if summary.get("market_date")!=day or summary.get("data_status")!="complete" or summary.get("symbols_ok")!=500:raise RuntimeError("Refusing stale or incomplete CN daily payload")
 key=os.environ.get("CN_BARK_KEY","").strip()
 if not key:raise RuntimeError("CN_BARK_KEY is not configured")
 marker=Path(".cache/cn-bark")/f"{day}.json"
 if marker.exists():
  saved=json.loads(marker.read_text(encoding="utf-8"))
  if saved.get("status")=="sent" and saved.get("market_date")==day:print(f"CN Bark already sent for {day}; duplicate skipped.");return 0
 signals=json.loads(Path("site/data/signals.json").read_text(encoding="utf-8"));names=list(dict.fromkeys(s["name"] for s in signals if s.get("name")))
 body="\n".join(" ".join(f"▰ {n} ▰" for n in names[i:i+4]) for i in range(0,len(names),4)) if names else "▰ No change ▰"
 server=os.environ.get("CN_BARK_SERVER","https://api.day.app").rstrip("/")
 payload=json.dumps({"device_key":key,"body":body,"level":"active"},ensure_ascii=False).encode()
 req=urllib.request.Request(server+"/push",data=payload,headers={"Content-Type":"application/json; charset=utf-8","User-Agent":"VEGAS-CN/1.0"},method="POST")
 with urllib.request.urlopen(req,timeout=25) as response:
  raw=response.read().decode("utf-8","replace")
  if response.status<200 or response.status>=300:raise RuntimeError(f"Bark HTTP {response.status}")
 result=json.loads(raw)
 if result.get("code")!=200:raise RuntimeError(f"Bark rejected push: {raw[:250]}")
 marker.parent.mkdir(parents=True,exist_ok=True);tmp=marker.with_suffix(".tmp")
 tmp.write_text(json.dumps({"market_date":day,"status":"sent","sent_at":now.isoformat()},ensure_ascii=False),encoding="utf-8");os.replace(tmp,marker)
 print(f"CN Bark sent: {len(names)} names for {day}");return 0
if __name__=="__main__":raise SystemExit(main())
