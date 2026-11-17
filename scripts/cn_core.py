from __future__ import annotations
from datetime import date
import numpy as np
import pandas as pd
PERIODS=(12,144,169,576,676)
COLUMNS=["date","open","high","low","close","volume","amount"]
def normalize_bars(frame):
    if frame is None or frame.empty:return pd.DataFrame(columns=COLUMNS)
    aliases={"日期":"date","开盘":"open","最高":"high","最低":"low","收盘":"close","成交量":"volume","成交额":"amount","vol":"volume"}
    x=frame.copy().rename(columns={k:v for k,v in aliases.items() if k in frame.columns and v not in frame.columns})
    for c in COLUMNS:
        if c not in x:x[c]=np.nan
    x["date"]=pd.to_datetime(x["date"],errors="coerce").dt.normalize()
    for c in COLUMNS[1:]:x[c]=pd.to_numeric(x[c],errors="coerce")
    return x[COLUMNS].dropna(subset=["date"]).drop_duplicates("date",keep="last").sort_values("date").reset_index(drop=True)
def validate_bars(frame):
    x=normalize_bars(frame)
    if x.empty:return x
    p=x[["open","high","low","close"]]
    valid=np.isfinite(p).all(axis=1)&p.gt(0).all(axis=1)
    valid &= x.high.ge(p[["open","close"]].max(axis=1))&x.low.le(p[["open","close"]].min(axis=1))&x.high.ge(x.low)
    valid &= np.isfinite(x[["volume","amount"]]).all(axis=1)&x.volume.ge(0)&x.amount.ge(0)
    return x.loc[valid].reset_index(drop=True)
def ema(values,span):
    if span not in PERIODS:raise ValueError(f"unsupported EMA period: {span}")
    return pd.to_numeric(values,errors="coerce").ewm(span=span,adjust=False,min_periods=span).mean()
def enrich_bars(frame):
    x=validate_bars(frame)
    for p in PERIODS:x[f"ema{p}"]=ema(x.close,p)
    return x
def touched_zones(row):
    found=[]
    for name,a,b in (("中锋",144,169),("红峰",576,676)):
        x,y=row.get(f"ema{a}"),row.get(f"ema{b}")
        if pd.notna(x) and pd.notna(y) and float(row.low)<=max(x,y) and float(row.high)>=min(x,y):found.append(name)
    return found
def scan_symbol(frame,code,name):
    x=enrich_bars(frame);pending=None;out=[];seen=set()
    for _,row in x.iterrows():
        zones=touched_zones(row)
        if zones:
            if pending is None:pending={"date":row.date.date().isoformat(),"zones":set()}
            pending["zones"].update(zones)
            continue
        if pending is None or pd.isna(row.ema12):continue
        close,line=float(row.close),float(row.ema12)
        side="上方" if close>line else "下方" if close<line else None
        if side is None:continue
        day=row.date.date().isoformat();key=(code,day,side)
        if key not in seen:
            out.append({"code":code,"name":name,"observation_date":pending["date"],"confirmation_date":day,"zones":sorted(pending["zones"]),"side":side,"close":round(close,4),"ema12":round(line,4)})
            seen.add(key)
        pending=None
    return out
def chart_rows(frame,limit=3000):
    x=enrich_bars(frame).tail(limit);rows=[]
    for _,r in x.iterrows():
        rows.append({k:(r[k].date().isoformat() if k=="date" else (None if pd.isna(r[k]) else round(float(r[k]),6))) for k in ["date","open","high","low","close","ema12","ema144","ema169","ema576","ema676"]})
    return rows
def within_history_limit(end:date,start:date)->bool:
    return start>=end.replace(year=end.year-10,day=min(end.day,28) if end.month==2 and end.day==29 else end.day)
