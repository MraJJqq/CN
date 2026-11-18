from __future__ import annotations
import argparse,base64,gzip,json,re,sys,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,datetime,time as clock_time
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import requests
from cn_core import normalize_bars,validate_bars,scan_symbol,chart_rows,within_history_limit
TZ=ZoneInfo("Asia/Shanghai");SOURCE="Tencent QFQ daily"
def symbols(path):
 raw=gzip.decompress(base64.b64decode(Path(path).read_text(encoding="ascii"))).decode().splitlines();codes=[x.strip() for x in raw if x.strip()]
 if len(codes)!=500 or len(set(codes))!=500 or any(not re.fullmatch(r"\d{6}",x) for x in codes):raise RuntimeError(f"CN500 invalid: {len(codes)} entries, {len(set(codes))} unique")
 return codes
def tencent_symbol(code):
 return ("sh" if code.startswith(("60","68","90")) else "sz" if code.startswith(("00","30")) else "bj")+code
def stock_names(codes):
 out={};session=requests.Session();session.headers.update({"Referer":"https://gu.qq.com/","User-Agent":"Mozilla/5.0"})
 for i in range(0,len(codes),50):
  chunk=codes[i:i+50];url="https://qt.gtimg.cn/q="+",".join("s_"+tencent_symbol(c) for c in chunk);last=None
  for attempt in range(4):
   try:
    r=session.get(url,timeout=25);r.raise_for_status()
    for m in re.finditer(r'v_s_(sh|sz|bj)(\d{6})="([^"]*)"',r.content.decode("gbk",errors="replace")):
     fields=m.group(3).split("~")
     if len(fields)>1 and fields[1].strip():out[m.group(2)]=fields[1].strip()
    last=None;break
   except Exception as e:
    last=e
    if attempt<3:time.sleep(2**attempt)
  if last:raise RuntimeError(f"Tencent name lookup failed for batch {i//50+1}: {last}")
  time.sleep(.15)
 missing=set(codes)-set(out)
 if missing:raise RuntimeError(f"Tencent name lookup incomplete: {len(out)}/500; missing={sorted(missing)[:12]}")
 return out
def fetch_one(code,end,start):
 import akshare as ak
 last=None
 for attempt in range(4):
  try:
   frame=ak.stock_zh_a_hist_tx(symbol=tencent_symbol(code),start_date=start.strftime("%Y%m%d"),end_date=end.strftime("%Y%m%d"),adjust="qfq")
   bars=validate_bars(normalize_bars(frame))
   if bars.empty:raise RuntimeError("Tencent returned no valid QFQ daily bars")
   if not within_history_limit(end,bars.date.min().date()):raise RuntimeError("returned history starts before requested 10-year boundary")
   return code,bars
  except Exception as e:
   last=e
   if attempt<3:time.sleep(min(12,2**attempt))
 raise RuntimeError(f"Tencent history failed after retries: {last}") from last
def publish(end,universe,names,frames,out):
 if len(universe)!=500 or len(frames)!=500 or set(frames)!=set(universe):raise RuntimeError("Refusing to publish partial CN500 data")
 signals=[]
 for code in universe:signals.extend(scan_symbol(frames[code],code,names[code]))
 today=end.isoformat();latest=[s for s in signals if s["confirmation_date"]==today]
 unique={(s["code"],s["confirmation_date"],s["side"]):s for s in latest};signals=sorted(unique.values(),key=lambda s:(s["code"],s["side"]))
 charts={s["code"]:chart_rows(frames[s["code"]]) for s in signals}
 summary={"source":SOURCE,"market_date":today,"universe_total":500,"symbols_ok":500,"signals_total":len(signals),"history_max_years":10,"frequency":"1D","adjust":"qfq","ema_periods":[12,144,169,576,676],"scan_completed_at":datetime.now(TZ).isoformat(),"data_status":"complete"}
 out.mkdir(parents=True,exist_ok=True)
 for name,obj in {"summary.json":summary,"signals.json":signals,"charts.json":charts}.items():
  target=out/name;tmp=target.with_suffix(target.suffix+".tmp");tmp.write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":")),encoding="utf-8");tmp.replace(target)
def main():
 p=argparse.ArgumentParser();p.add_argument("--universe",default="config/cn500.codes.gz.b64");p.add_argument("--output",default="site/data");p.add_argument("--workers",type=int,default=6);p.add_argument("--date",default=datetime.now(TZ).date().isoformat());a=p.parse_args()
 end=date.fromisoformat(a.date);now=datetime.now(TZ)
 if end==now.date() and now.time().replace(tzinfo=None)<clock_time(15,30):raise RuntimeError("Refusing scan before 15:30 China time")
 start=end.replace(year=end.year-10,day=min(end.day,28) if end.month==2 and end.day==29 else end.day)
 universe=symbols(a.universe);names=stock_names(universe);frames={};errors=[]
 with ThreadPoolExecutor(max_workers=max(1,min(a.workers,8))) as pool:
  jobs={pool.submit(fetch_one,c,end,start):c for c in universe}
  for f in as_completed(jobs):
   code=jobs[f]
   try:got,bars=f.result();frames[got]=bars
   except Exception as exc:errors.append(f"{code}: {type(exc).__name__}: {exc}");print(errors[-1],file=sys.stderr,flush=True)
 if errors or len(frames)!=500:raise RuntimeError(f"CN500 aborted without publishing: {len(frames)}/500 successful; {len(errors)} failures")
 publish(end,universe,names,frames,Path(a.output));print(f"Complete Tencent QFQ CN500 daily scan: {end}, 500/500.")
if __name__=="__main__":raise SystemExit(main())
