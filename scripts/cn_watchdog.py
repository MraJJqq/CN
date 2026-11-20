"""CN daily-scan watchdog with one bounded recovery per A-share session."""
import json,os,urllib.request
from datetime import datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Shanghai")
DUE=time(15,35)
GRACE_MINUTES=15
def _api():
 repo=os.environ.get("GITHUB_REPOSITORY","").strip()
 if repo.count("/")!=1:raise RuntimeError("GITHUB_REPOSITORY must be owner/repository")
 return "https://api.github.com/repos/"+repo
def _headers():
 token=os.environ.get("GH_TOKEN","").strip()
 if not token:raise RuntimeError("GH_TOKEN required")
 return {"Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28"}
def _request(url,method="GET",payload=None):
 data=None if payload is None else json.dumps(payload).encode()
 headers=_headers()
 if payload is not None:headers["Content-Type"]="application/json"
 req=urllib.request.Request(url,data=data,headers=headers,method=method)
 with urllib.request.urlopen(req,timeout=20) as response:
  raw=response.read()
  return json.loads(raw) if raw else None
def _created(item):return datetime.fromisoformat(item["created_at"].replace("Z","+00:00"))
def _issue(issues,title):return next((x for x in issues if not x.get("pull_request") and x.get("title")==title),None)
def _close_lock(api,issues,lock):
 _request(api+f"/issues/{lock['number']}","PATCH",{"state":"closed"})
 issues[:]=[x for x in issues if x.get("number")!=lock.get("number")]
def _dispatch(api,issues,marker,day):
 title=f"[CN Watchdog Recovery Lock] {day}"
 lock=_request(api+"/issues","POST",{"title":title,"body":f"Durable CN recovery lock: {marker}. Created before dispatch to prevent duplicate recoveries."})
 if not lock or "number" not in lock:raise RuntimeError("Could not create CN recovery lock")
 issues.append(lock)
 try:
  _request(api+"/actions/workflows/a-share-daily.yml/dispatches","POST",{"ref":"main","inputs":{"recovery_slot":marker}})
  print(f"CN {day} recovery dispatched.")
 except Exception as exc:print(f"CN {day} recovery dispatch ambiguous; lock retained: {exc}")
def main(now=None):
 api=_api()
 current=(now or datetime.now(timezone.utc)).astimezone(TZ)
 due_time=(datetime.combine(current.date(),DUE)+timedelta(minutes=GRACE_MINUTES)).time()
 if current.weekday()>=5 or current.time()<due_time:
  print("CN daily scan is not due for recovery.");return 0
 from scripts.trading_calendar import is_a_share_trading_day
 if not is_a_share_trading_day(current.date()):
  print("A-share exchange holiday; recovery skipped.");return 0
 day=current.date().isoformat()
 slot=datetime.combine(current.date(),DUE,tzinfo=TZ)
 marker="recovery:"+slot.strftime("%Y%m%d-%H%M")
 title=f"[CN Watchdog Recovery Lock] {day}"
 runs=(_request(api+"/actions/workflows/a-share-daily.yml/runs?per_page=100") or {}).get("workflow_runs",[])
 issues=_request(api+"/issues?state=open&per_page=100") or []
 lock=_issue(issues,title)
 start=slot.astimezone(timezone.utc)-timedelta(minutes=GRACE_MINUTES)
 scheduled=[]
 recoveries=[]
 for run in runs:
  created=_created(run)
  if not start<=created<start+timedelta(days=1):continue
  if run.get("event")=="schedule":scheduled.append(run)
  elif run.get("event")=="workflow_dispatch" and marker in (run.get("display_title") or ""):recoveries.append(run)
 if recoveries:
  latest=max(recoveries,key=lambda x:x["created_at"])
  if latest.get("status")!="completed":
   print("CN recovery scan is running.");return 0
  if lock:_close_lock(api,issues,lock)
  if latest.get("conclusion")=="success":
   print("CN recovery scan completed successfully.");return 0
  alert_title="[CN Watchdog] Daily scan recovery failed"
  if not _issue(issues,alert_title):
   _request(api+"/issues","POST",{"title":alert_title,"body":f"CN daily recovery failed for {day}. Latest run #{latest.get('run_number')} concluded {latest.get('conclusion')}."})
  print("CN recovery failed; alert issue created.");return 0
 if scheduled:
  latest=max(scheduled,key=lambda x:x["created_at"])
  if latest.get("status")!="completed":
   print("CN scheduled scan is running.");return 0
  if latest.get("conclusion")=="success":
   if lock:_close_lock(api,issues,lock)
   print("CN daily scan completed successfully.");return 0
  if lock:
   age=current.astimezone(timezone.utc)-_created(lock)
   if age<timedelta(minutes=20):
    print("CN recovery lock active; awaiting GitHub recovery-run registration.");return 0
   alert_title="[CN Watchdog] Daily scan recovery failed"
   if not _issue(issues,alert_title):
    _request(api+"/issues","POST",{"title":alert_title,"body":f"CN recovery dispatch for {day} was not registered within 20 minutes; lock retained for manual inspection."})
   print("CN recovery dispatch registration timed out; alert issue created.");return 0
  _dispatch(api,issues,marker,day);return 0
 if lock:
  age=current.astimezone(timezone.utc)-_created(lock)
  print("CN recovery lock active; awaiting GitHub run registration." if age<timedelta(minutes=20) else "CN recovery dispatch registration timed out; lock retained for manual inspection.")
  return 0
 _dispatch(api,issues,marker,day)
 return 0
if __name__=="__main__":raise SystemExit(main())
