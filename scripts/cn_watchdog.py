"""CN daily-scan watchdog with one bounded recovery per A-share session."""
from __future__ import annotations
import json, os, urllib.request
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Shanghai"); DUE=time(15,35); GRACE_MINUTES=15; LOCK_TIMEOUT_MINUTES=20
def recovery_marker(day):
    return "recovery:"+datetime.combine(day,DUE,tzinfo=TZ).strftime("%Y%m%d-%H%M")
def recovery_is_due(current):
    local=current.astimezone(TZ); due=(datetime.combine(local.date(),DUE)+timedelta(minutes=GRACE_MINUTES)).time()
    return local.weekday()<5 and local.time().replace(tzinfo=None)>=due

def recovery_session_day(current, is_trading_day, previous_trading_day):
    """Return the latest completed session whose recovery grace period has elapsed."""
    local=current.astimezone(TZ)
    today=local.date()
    if not is_trading_day(today):
        return None
    cutoff=(datetime.combine(today,DUE)+timedelta(minutes=GRACE_MINUTES)).time()
    candidate=today if local.time().replace(tzinfo=None)>=cutoff else previous_trading_day(today)
    due_at=datetime.combine(candidate,DUE,tzinfo=TZ)+timedelta(minutes=GRACE_MINUTES)
    return candidate if local>=due_at else None
def _api():
    repo=os.environ.get("GITHUB_REPOSITORY","").strip()
    if repo.count("/")!=1: raise RuntimeError("GITHUB_REPOSITORY must be owner/repository")
    return "https://api.github.com/repos/"+repo
def _headers():
    token=os.environ.get("GH_TOKEN","").strip()
    if not token: raise RuntimeError("GH_TOKEN required")
    return {"Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"X-GitHub-Api-Version":"2022-11-28"}
def _request(url,method="GET",payload=None):
    data=None if payload is None else json.dumps(payload).encode(); headers=_headers()
    if payload is not None: headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=20) as response:
        raw=response.read(); return json.loads(raw) if raw else None
def _created(item): return datetime.fromisoformat(item["created_at"].replace("Z","+00:00"))
def _issue(issues,title):
    return next((x for x in issues if not x.get("pull_request") and x.get("title")==title),None)
def _close_lock(api,issues,lock):
    _request(api+f"/issues/{lock['number']}","PATCH",{"state":"closed"})
    issues[:]=[x for x in issues if x.get("number")!=lock.get("number")]
def _alert_once(api,issues,title,body):
    if not _issue(issues,title): _request(api+"/issues","POST",{"title":title,"body":body})
def _dispatch(api,issues,marker,day):
    title=f"[CN Watchdog Recovery Lock] {day}"
    lock=_request(api+"/issues","POST",{"title":title,"body":f"Durable CN recovery lock: {marker}. Created before dispatch to prevent duplicate recoveries."})
    if not lock or "number" not in lock: raise RuntimeError("Could not create CN recovery lock")
    issues.append(lock)
    try:
        _request(api+"/actions/workflows/a-share-daily.yml/dispatches","POST",{"ref":"main","inputs":{"recovery_slot":marker}})
        print(f"CN {day} recovery dispatched.")
    except Exception as exc: print(f"CN {day} recovery dispatch ambiguous; lock retained: {exc}")
def main(now=None):
    api=_api(); current=(now or datetime.now(timezone.utc)).astimezone(TZ)
    from scripts.trading_calendar import is_a_share_trading_day, previous_a_share_trading_day
    day=recovery_session_day(current,is_a_share_trading_day,previous_a_share_trading_day)
    if day is None:
        print("CN daily scan is not due for recovery."); return 0
    day_text=day.isoformat(); marker=recovery_marker(day)
    lock_title=f"[CN Watchdog Recovery Lock] {day_text}"
    alert_title="[CN Watchdog] Daily scan recovery failed"
    timeout_title=f"[CN Watchdog] Recovery dispatch registration timed out ({day_text})"
    runs=(_request(api+"/actions/workflows/a-share-daily.yml/runs?per_page=100") or {}).get("workflow_runs",[])
    issues=_request(api+"/issues?state=open&per_page=100") or []; lock=_issue(issues,lock_title)
    slot=datetime.combine(day,DUE,tzinfo=TZ)
    start=slot.astimezone(timezone.utc)-timedelta(minutes=GRACE_MINUTES)
    end=datetime.combine(day+timedelta(days=1),time.min,tzinfo=TZ).astimezone(timezone.utc)
    scheduled=[]; recoveries=[]
    for run in runs:
        created=_created(run)
        if not start<=created<end: continue
        if run.get("event")=="schedule": scheduled.append(run)
        elif run.get("event")=="workflow_dispatch" and marker in (run.get("display_title") or ""): recoveries.append(run)
    if recoveries:
        latest=max(recoveries,key=lambda x:x["created_at"])
        if latest.get("status")!="completed":
            print("CN recovery scan is running."); return 0
        if latest.get("conclusion")=="success":
            if lock: _close_lock(api,issues,lock)
            print("CN recovery scan completed successfully."); return 0
        _alert_once(api,issues,alert_title,f"CN daily recovery failed for {day_text}. Latest run #{latest.get('run_number')} concluded {latest.get('conclusion')}.")
        print("CN recovery failed; alert issue created."); return 0
    if scheduled:
        latest=max(scheduled,key=lambda x:x["created_at"])
        if latest.get("status")!="completed":
            print("CN scheduled scan is running."); return 0
        if latest.get("conclusion")=="success":
            if lock: _close_lock(api,issues,lock)
            print("CN daily scan completed successfully."); return 0
    if lock:
        age=current.astimezone(timezone.utc)-_created(lock)
        if age<timedelta(minutes=LOCK_TIMEOUT_MINUTES):
            print("CN recovery lock active; awaiting GitHub recovery-run registration."); return 0
        _alert_once(api,issues,timeout_title,f"CN recovery dispatch for {day_text} was not registered within {LOCK_TIMEOUT_MINUTES} minutes. Lock retained; automatic retry is disabled.")
        print("CN recovery dispatch registration timed out; alert issue created."); return 0
    _dispatch(api,issues,marker,day_text); return 0
if __name__=="__main__": raise SystemExit(main())
