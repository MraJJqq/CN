from __future__ import annotations
import argparse,json,re,sys
from datetime import date,datetime,timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
TZ=ZoneInfo("Asia/Shanghai");URL="https://www.sse.com.cn/disclosure/dealinstruc/closed/"
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style","noscript"):self.skip+=1
 def handle_endtag(self,tag):
  if tag in ("script","style","noscript") and self.skip:self.skip-=1
 def handle_data(self,data):
  if not self.skip and data.strip():self.parts.append(data.strip())
def closed_days(year):
 r=requests.get(URL,headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.sse.com.cn/"},timeout=25);r.raise_for_status();p=Text();p.feed(r.text);text=re.sub(r"\s+"," "," ".join(p.parts))
 m=re.search(rf"{year}\s*年\s*休市安排",text)
 if not m:raise RuntimeError(f"Official SSE calendar for {year} not published")
 tail=text[m.end():];n=re.search(r"(?:\d{4}\s*年\s*休市安排|相关公告)",tail);section=tail[:n.start()] if n else tail;days=set()
 for pat,rng in [(r"(\d{1,2})月(\d{1,2})日\s*(?:（星期[一二三四五六日天]）)?\s*至\s*(\d{1,2})月(\d{1,2})日\s*(?:（星期[一二三四五六日天]）)?\s*休市",True),(r"(\d{1,2})月(\d{1,2})日\s*(?:（星期[一二三四五六日天]）)?\s*(?:为)?\s*(?:周末)?休市",False)]:
  for x in re.finditer(pat,section):
   v=list(map(int,x.groups()));d=date(year,v[0],v[1]);end=date(year,v[2],v[3]) if rng else d
   while d<=end:days.add(d);d+=timedelta(days=1)
 if not days:raise RuntimeError(f"Could not parse SSE closure schedule for {year}")
 return days
def is_trading_day(d):
 if d.weekday()>=5:return False
 return d not in closed_days(d.year)
def main():
 p=argparse.ArgumentParser();p.add_argument("--date",default=datetime.now(TZ).date().isoformat());p.add_argument("--write",default="site/data/trading-calendar.json");p.add_argument("--github-output",default="");a=p.parse_args();d=date.fromisoformat(a.date);trading=is_trading_day(d)
 obj={"date":d.isoformat(),"timezone":"Asia/Shanghai","is_trading_day":trading,"calendar_source":"Shanghai Stock Exchange official holiday schedule","calendar_url":URL,"checked_at":datetime.now(TZ).isoformat()}
 out=Path(a.write);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
 if a.github_output:
  with open(a.github_output,"a",encoding="utf-8") as f:f.write(f"is-trading-day={'true' if trading else 'false'}\ntrade-date={d.isoformat()}\n")
 print(json.dumps(obj,ensure_ascii=False))
if __name__=="__main__":
 try:main()
 except Exception as e:print(f"Exchange calendar unavailable; fail closed: {e}",file=sys.stderr);raise
