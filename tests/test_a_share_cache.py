import unittest
import pandas as pd
import json
import gzip
import tempfile
from pathlib import Path
from datetime import date,datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from scripts.trading_calendar import is_a_share_trading_day,previous_a_share_trading_day,upcoming_trading_days,exchange_closed_days,latest_completed_session as calendar_latest_completed_session
from scripts.a_share_cache import require_complete_fetch,fetch_cached,cache_paths,atomic_json,SOURCE,SCHEMA,latest_completed_session,build_scan_diagnostics,analyze_one
from scripts.push_signals import bark_marker_path,notification_already_sent,record_notification_sent
from scripts.a_share_cache import to_tencent_symbol,parse_tencent_quote_text,merge_frames,through_date,valid_bars,excluded_name,ema,normalize
from scripts.validate_pages_payload import validate_payload

OFFICIAL_SSE_2026 = """2026年休市安排 元旦：1月1日（星期四）至1月3日（星期六）休市，1月5日（星期一）起照常开市。另外，1月4日（星期日）为周末休市。春节：2月15日（星期日）至2月23日（星期一）休市，2月24日（星期二）起照常开市。另外，2月14日（星期六）、2月28日（星期六）为周末休市。清明节：4月4日（星期六）至4月6日（星期一）休市，4月7日（星期二）起照常开市。劳动节：5月1日（星期五）至5月5日（星期二）休市，5月6日（星期三）起照常开市。另外，5月9日（星期六）为周末休市。端午节：6月19日（星期五）至6月21日（星期日）休市，6月22日（星期一）起照常开市。中秋节：9月25日（星期五）至9月27日（星期日）休市，9月28日（星期一）起照常开市。国庆节：10月1日（星期四）至10月7日（星期三）休市，10月8日（星期四）起照常开市。另外，9月20日（星期日）、10月10日（星期六）为周末休市。相关公告"""

class TradingCalendarTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.calendar_patch=patch("scripts.trading_calendar._fetch_exchange_calendar_page",return_value=OFFICIAL_SSE_2026)
  cls.calendar_patch.start();exchange_closed_days.cache_clear()
 @classmethod
 def tearDownClass(cls):
  cls.calendar_patch.stop();exchange_closed_days.cache_clear()
 def test_delayed_scheduled_run_after_midnight_uses_latest_completed_session(self):
  now=datetime(2026,11,21,0,18,tzinfo=ZoneInfo("Asia/Shanghai"))
  self.assertEqual(calendar_latest_completed_session(now),date(2026,11,20))
 def test_after_close_uses_current_completed_session(self):
  now=datetime(2026,11,12,16,30,tzinfo=ZoneInfo("Asia/Shanghai"))
  self.assertEqual(latest_completed_session(date(2026,11,12),now),date(2026,11,12))
 def test_before_close_uses_previous_completed_session(self):
  now=datetime(2026,11,12,14,59,tzinfo=ZoneInfo("Asia/Shanghai"))
  self.assertEqual(latest_completed_session(date(2026,11,12),now),date(2026,11,11))
 def test_non_trading_day_uses_previous_session_even_after_close(self):
  now=datetime(2026,11,14,16,30,tzinfo=ZoneInfo("Asia/Shanghai"))
  self.assertEqual(latest_completed_session(date(2026,11,14),now),date(2026,11,13))
 def test_unpublished_year_fails_closed(self):
  with patch("scripts.trading_calendar._fetch_exchange_calendar_page",return_value=OFFICIAL_SSE_2026):
   with self.assertRaisesRegex(RuntimeError,"does not publish 2027"):
    exchange_closed_days(2027)
 def test_official_exchange_holiday_range_is_parsed(self):
  closed=exchange_closed_days(2026)
  self.assertIn(date(2026,10,1),closed);self.assertIn(date(2026,10,7),closed)
  self.assertNotIn(date(2026,10,8),closed)
 def test_weekend_is_not_a_trading_day(self):
  self.assertFalse(is_a_share_trading_day(date(2026, 11, 7)))
 def test_public_holiday_is_not_a_trading_day(self):
  self.assertFalse(is_a_share_trading_day(date(2026, 10, 1)))
 def test_normal_weekday_is_a_trading_day(self):
  self.assertTrue(is_a_share_trading_day(date(2026, 11, 10)))
 def test_previous_session_skips_public_holiday(self):
  self.assertEqual(previous_a_share_trading_day(date(2026, 10, 8)),date(2026, 9, 30))
 def test_upcoming_sessions_skip_public_holiday(self):
  self.assertEqual(upcoming_trading_days(date(2026, 10, 1),1),["2026-10-08"])
 def test_partial_fetch_is_rejected(self):
  with self.assertRaisesRegex(RuntimeError,"refusing partial CN500 publish"):
   require_complete_fetch([{"symbol":"sh600000","reason":"network timeout"}])
 def test_complete_fetch_is_accepted(self):
  require_complete_fetch([])

class TencentCacheTests(unittest.TestCase):
 def test_symbol_map(self):
  self.assertEqual(to_tencent_symbol("600000"),"sh600000")
  self.assertEqual(to_tencent_symbol("000001"),"sz000001")
  self.assertEqual(to_tencent_symbol("sh.600000"),"sh600000")
  self.assertEqual(to_tencent_symbol("830001"),"bj830001")
  with self.assertRaises(ValueError):to_tencent_symbol("ABC")
 def test_schema(self):
  x=normalize(pd.DataFrame([{"date":"2024-01-02","open":10,"high":11,"low":9,"close":10,"volume":100,"amount":1000}]))
  self.assertEqual(list(x.columns),["date","open","high","low","close","volume","amount"]);self.assertEqual(len(x),1)
 def test_overlap_merge(self):
  cols=["date","open","high","low","close","volume","amount"]
  a=pd.DataFrame([["2024-01-02",10,11,9,10,100,1000]],columns=cols)
  b=pd.DataFrame([["2024-01-02",10,12,9,11,120,1200],["2024-01-03",11,12,10,11,110,1100]],columns=cols)
  m=merge_frames(a,b);self.assertEqual(len(m),2);self.assertEqual(float(m.iloc[0].close),11)
 def test_cache_trims_in_progress_or_future_dates(self):
  cols=["date","open","high","low","close","volume","amount"]
  x=pd.DataFrame([["2024-01-02",10,11,9,10,100,1000],["2024-01-03",11,12,10,11,110,1100]],columns=cols)
  m=through_date(x,"2024-01-02")
  self.assertEqual(len(m),1);self.assertEqual(str(m.iloc[0].date.date()),"2024-01-02")
 def test_invalid_ohlc(self):
  cols=["date","open","high","low","close","volume","amount"]
  x=pd.DataFrame([["2024-01-02",10,11,9,10,100,1000],["2024-01-03",10,9,11,10,100,1000]],columns=cols)
  self.assertEqual(len(valid_bars(x)),1)
 def test_invalid_turnover_is_rejected(self):
  cols=["date","open","high","low","close","volume","amount"]
  x=pd.DataFrame([["2024-01-02",10,11,9,10,100,1000],["2024-01-03",10,11,9,10,-1,1000],["2024-01-04",10,11,9,10,100,None]],columns=cols)
  self.assertEqual(len(valid_bars(x)),1)
 def test_ema(self):
  x=ema(pd.Series(range(1,20),dtype=float),12);self.assertTrue(pd.isna(x.iloc[10]));self.assertTrue(pd.notna(x.iloc[11]))
 def test_names(self):
  self.assertTrue(excluded_name("ST某某"));self.assertTrue(excluded_name("某某退"));self.assertFalse(excluded_name("贵州茅台"))
 def test_corrupt_cache_is_rebuilt_from_tencent(self):
  with tempfile.TemporaryDirectory() as directory:
   data,meta=cache_paths(directory,"sh600000")
   data.write_bytes(b"not a gzip file")
   atomic_json(meta,{"schema_version":SCHEMA,"source":SOURCE,"adjust":"qfq","symbol":"sh600000","frequency":"daily","complete":True})
   fresh=pd.DataFrame([{"date":"2024-01-02","open":10,"high":11,"low":9,"close":10,"volume":100,"amount":1000}])
   with patch("scripts.a_share_cache.fetch_tencent",return_value=fresh) as fetch:
    bars,info=fetch_cached("sh600000","2024-01-02",directory)
   self.assertEqual(len(bars),1)
   self.assertEqual(fetch.call_args.args[1],"20140102")
   self.assertTrue(info["complete"])
   self.assertEqual(len(pd.read_csv(data,compression="gzip")),1)
   self.assertTrue(json.loads(meta.read_text(encoding="utf-8"))["complete"])

class ScanDiagnosticsTests(unittest.TestCase):
 def test_scan_diagnostics_report_freshness_and_stale_history(self):
  with tempfile.TemporaryDirectory() as directory:
   Path(directory,"sh600000.meta.json").write_text("{}",encoding="utf-8")
   result=build_scan_diagnostics([{"last_date":"2026-11-16"},{"last_date":"2026-11-13"}],[{"reason":"stale_history"},{"reason":"ST_or_delisted_name"}],directory,0)
   self.assertEqual(result["stale_history_count"],1)
   self.assertEqual(result["oldest_eligible_data_date"],"2026-11-13")
   self.assertEqual(result["latest_eligible_data_date"],"2026-11-16")
   self.assertEqual(result["cache_symbol_count"],1)
   self.assertGreaterEqual(result["scan_duration_seconds"],0)

class BarkDeduplicationTests(unittest.TestCase):
 def test_daily_marker_prevents_duplicate_notification(self):
  with tempfile.TemporaryDirectory() as directory:
   self.assertFalse(notification_already_sent("2026-11-16",directory))
   marker=record_notification_sent("2026-11-16",3,directory)
   self.assertTrue(marker.exists())
   self.assertTrue(notification_already_sent("2026-11-16",directory))
   self.assertFalse(notification_already_sent("2026-11-17",directory))

class TencentNameParserTests(unittest.TestCase):
 def test_parse_tencent_quote_text(self):
  raw='v_s_sh600000="1~浦发银行~600000~10.0";v_s_sz000001="1~平安银行~000001~11.0";'
  names=parse_tencent_quote_text(raw)
  self.assertEqual(names["sh600000"],"浦发银行")
  self.assertEqual(names["sz000001"],"平安银行")

class AShareSignalRuleTests(unittest.TestCase):
 def _analyze(self, closes, ema12, mid=(100.0,100.2), red=(200.0,200.2)):
  dates=pd.date_range("2026-11-09",periods=len(closes),freq="B")
  bars=pd.DataFrame({"date":dates,"open":closes,"high":[x+0.5 for x in closes],"low":[x-0.5 for x in closes],"close":closes,"volume":[1000]*len(closes),"amount":[100000]*len(closes)})
  def fake_ema(values,period):
   selected={12:ema12,144:[mid[0]]*len(values),169:[mid[1]]*len(values),576:[red[0]]*len(values),676:[red[1]]*len(values)}[period]
   return pd.Series(selected,index=values.index,dtype=float)
  with patch("scripts.a_share_cache.fetch_cached",return_value=(bars,{})),patch("scripts.a_share_cache.ema",side_effect=fake_ema):
   return analyze_one({"symbol":"sh600000","name":"浦发银行"},dates[-1].date().isoformat(),"unused")
 def test_touch_direction_short_then_close_below_ema12(self):
  result=self._analyze([90,90,100,94],[95,95,95,95])
  self.assertEqual(len(result["signals"]),1)
  signal=result["signals"][0]
  self.assertEqual(signal["observation_date"],"2026-11-11")
  self.assertEqual(signal["confirmation_date"],"2026-11-12")
  self.assertEqual(signal["confirmation_side"],"下方")
 def test_touch_direction_long_then_close_above_ema12(self):
  result=self._analyze([110,110,100,106],[105,105,105,105])
  self.assertEqual(len(result["signals"]),1)
  self.assertEqual(result["signals"][0]["confirmation_side"],"上方")
 def test_observation_has_no_expiry(self):
  result=self._analyze([90,90,100,101,102,94],[95]*6)
  self.assertEqual(len(result["signals"]),1)
  self.assertEqual(result["signals"][0]["confirmation_date"],"2026-11-16")
 def test_wrong_direction_does_not_trigger(self):
  result=self._analyze([90,90,100,110,94],[95]*5)
  self.assertEqual(len(result["signals"]),1)
  self.assertEqual(result["signals"][0]["confirmation_date"],"2026-11-13")
  self.assertEqual(result["signals"][0]["confirmation_side"],"下方")
 def test_same_day_mid_and_red_touch_merge(self):
  result=self._analyze([90,90,100,94],[95]*4,mid=(100.0,100.2),red=(100.0,100.2))
  self.assertEqual(len(result["signals"]),1)
  self.assertEqual(result["signals"][0]["observation_zone"],"中锋,红峰")
 def test_rearm_requires_price_to_leave_zone_before_next_touch(self):
  result=self._analyze([90,90,100,94,100,94,90,100,94],[95]*9)
  self.assertEqual(len(result["signals"]),2)
 def test_touch_without_directional_ema12_confirmation_does_not_signal(self):
  result=self._analyze([90,90,100,101,102],[95]*5)
  self.assertEqual(result["signals"],[])
 def test_ema_matches_v12_recursive_ewm(self):
  values=pd.Series(range(1,30),dtype=float)
  expected=values.ewm(span=12,adjust=False,min_periods=12).mean()
  pd.testing.assert_series_equal(ema(values,12),expected)

class PagesPayloadValidationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.calendar_patch=patch("scripts.trading_calendar._fetch_exchange_calendar_page",return_value=OFFICIAL_SSE_2026)
  cls.calendar_patch.start();exchange_closed_days.cache_clear()
 @classmethod
 def tearDownClass(cls):
  cls.calendar_patch.stop();exchange_closed_days.cache_clear()
 def _write_payload(self, root, dates=("2026-11-09","2026-11-06","2026-11-09"), fetch_errors=0, bad_chart=False):
  data=Path(root)/"data";charts=data/"charts";charts.mkdir(parents=True)
  cards=[{"symbol":f"CN{i:03d}","status":"ready","latest_close":10.0,"previous_close":9.5} for i in range(500)]
  universe=[]
  for i,last_date in enumerate(dates):
   symbol=f"sh60000{i}"
   universe.append({"symbol":symbol,"last_date":last_date})
   chart={"symbol":symbol,"last_date":("2026-11-05" if bad_chart and i==0 else last_date),"ema_schema":2,"ema_periods":[12,144,169,576,676],"ema_source":"full-history-per-bar","bars":[[last_date,10,11,9,10,*([10]*5)]]}
   with gzip.open(charts/(symbol+".json.gz"),"wt",encoding="utf-8") as handle:json.dump(chart,handle)
  summary={"universe_size":500,"eligible_count":len(universe),"fetch_error_count":fetch_errors,"market_date":max(dates),"previous_market_date":"2026-11-06","today_signal_count":1,"previous_signal_count":0,"web_ema_policy":"EMA12/144/169/576/676 calculated from the full available 10-year Tencent history and aligned to displayed bars"}
  payloads={"cards.json":cards,"summary.json":summary,"universe.json":universe,"signals.json":[{"symbol":universe[0]["symbol"],"confirmation_date":summary["market_date"]}],"signals.previous.json":[],"trading-calendar.json":{"trading_days":[summary["market_date"]]}}
  for name,value in payloads.items():(data/name).write_text(json.dumps(value),encoding="utf-8")
  return data
 def test_allows_eligible_stocks_with_older_last_dates(self):
  with tempfile.TemporaryDirectory() as directory:
   result=validate_payload(self._write_payload(directory),expected_market_date="2026-11-09")
   self.assertEqual(result["market_date"],"2026-11-09")
   self.assertEqual(result["eligible"],3)
 def test_allows_unavailable_card_without_quote(self):
  with tempfile.TemporaryDirectory() as directory:
   data=self._write_payload(directory)
   cards=json.loads((data/"cards.json").read_text(encoding="utf-8"))
   cards[0]={"symbol":cards[0]["symbol"],"status":"unavailable","reason":"ST_or_delisted_name"}
   (data/"cards.json").write_text(json.dumps(cards),encoding="utf-8")
   self.assertEqual(validate_payload(data)["cards"],500)
 def test_rejects_ready_card_without_quote(self):
  with tempfile.TemporaryDirectory() as directory:
   data=self._write_payload(directory)
   cards=json.loads((data/"cards.json").read_text(encoding="utf-8"))
   cards[0].pop("latest_close")
   (data/"cards.json").write_text(json.dumps(cards),encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"Ready CN500 card"):
    validate_payload(data)
 def test_rejects_calendar_missing_market_date(self):
  with tempfile.TemporaryDirectory() as directory:
   data=self._write_payload(directory)
   (data/"trading-calendar.json").write_text(json.dumps({"trading_days":[]}),encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"missing from the official trading calendar"):
    validate_payload(data)
 def test_rejects_tencent_fetch_errors(self):
  with tempfile.TemporaryDirectory() as directory:
   with self.assertRaisesRegex(ValueError,"Tencent fetch errors"):validate_payload(self._write_payload(directory,fetch_errors=1))
 def test_rejects_chart_date_mismatch(self):
  with tempfile.TemporaryDirectory() as directory:
   with self.assertRaisesRegex(ValueError,"date-mismatched"):validate_payload(self._write_payload(directory,bad_chart=True))
 def test_rejects_wrong_previous_market_date(self):
  with tempfile.TemporaryDirectory() as directory:
   data=self._write_payload(directory)
   summary=json.loads((data/"summary.json").read_text(encoding="utf-8"))
   summary["previous_market_date"]="2026-11-05"
   (data/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"official prior SSE session"):
    validate_payload(data,expected_market_date="2026-11-09")

 def test_rejects_stale_market_date_even_when_payload_is_internally_consistent(self):
  with tempfile.TemporaryDirectory() as directory:
   with self.assertRaisesRegex(ValueError,"latest completed SSE session"):
    validate_payload(self._write_payload(directory),expected_market_date="2026-11-10")

 def test_rejects_summary_market_date_not_newest(self):
  with tempfile.TemporaryDirectory() as directory:
   data=self._write_payload(directory)
   summary=json.loads((data/"summary.json").read_text(encoding="utf-8"));summary["market_date"]="2026-11-06"
   (data/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"newest eligible-stock date"):validate_payload(data,expected_market_date="2026-11-09")

class WorkflowReliabilityTests(unittest.TestCase):
 def test_frontend_publish_is_decoupled_from_tencent_scan(self):
  root=Path(__file__).resolve().parents[1]
  scan=(root/".github/workflows/a-share-daily.yml").read_text(encoding="utf-8")
  publish=(root/".github/workflows/pages-publish.yml").read_text(encoding="utf-8")
  self.assertNotIn('      - "site/**"',scan)
  self.assertIn('      - "site/**"',publish)
  self.assertIn('cron: "35 7 * * 1-5"',scan)
  self.assertNotIn("  push:",scan)
  self.assertIn("  workflow_dispatch:",scan)
  self.assertNotIn("Gate manual scans until after the A-share close",scan)
  self.assertNotIn("scan-window.outputs.allowed",scan)
  self.assertIn("if: steps.calendar.outputs.is-trading-day == 'true'",scan)
  self.assertIn("steps.scan.outcome != 'skipped'",scan)
  self.assertIn("steps.validate.outcome == 'success'",scan)
  self.assertIn("Check Bark credentials",scan)
  self.assertIn("steps.bark.outputs.configured == 'true'",scan)
  self.assertIn("continue-on-error: true",scan)
  self.assertIn("steps.bark-push.outcome == 'failure'",scan)
  self.assertIn("if: always() && needs.scan-and-cache.outputs.has-data",scan)
  self.assertIn("--latest-completed-session",scan)
  self.assertIn('--as-of "${{ steps.calendar.outputs.trade-date }}"',scan)
  self.assertIn("--allow-previous-snapshot --data-dir",publish)
  self.assertIn("--limit 1000",publish)
  self.assertIn("refs/heads/cn-data",scan)
  self.assertIn("origin/cn-data",publish)
  self.assertIn("requirements-watchdog.txt",(root/".github/workflows/cn-watchdog.yml").read_text(encoding="utf-8"))
  self.assertNotIn("rm -rf .cn-data-artifact site/data",publish)
  self.assertNotIn("rm -rf .cc-data-artifact",publish)
  self.assertIn("cancel-in-progress: false",scan)
  self.assertIn("cancel-in-progress: false",publish)
 def test_bark_only_runs_after_payload_validation(self):
  root=Path(__file__).resolve().parents[1]
  scan=(root/".github/workflows/a-share-daily.yml").read_text(encoding="utf-8")
  self.assertLess(scan.index("Validate complete Pages data payload"),scan.index("Push CN500 daily signals to Bark"))
  self.assertIn("python scripts/validate_pages_payload.py",scan)

if __name__=="__main__":unittest.main()
