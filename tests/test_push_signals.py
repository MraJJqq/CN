from __future__ import annotations
import sys,tempfile,unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from push_signals import BARK_TITLE,format_bark_body,is_recovery_dispatch,notification_market_date,record_notification_sent,should_skip_duplicate,should_skip_non_trading_day,validate_signal_rows
class BarkNotificationPolicyTests(unittest.TestCase):
    def test_bark_template_matches_vegasbark(self):
        self.assertEqual(BARK_TITLE,"▸▸ 𝐕𝐞𝐠𝐚𝐬 𝐒𝐢𝐠𝐧𝐚𝐥 ◂◂")
        self.assertEqual(format_bark_body(["AAPL","NVDA"]), "AAPL ▰\u00a0NVDA")
        self.assertEqual(format_bark_body([]), "𝐍𝐨 𝐒𝐢𝐠𝐧𝐚𝐥")
    def test_manual_run_uses_latest_completed_session_before_close(self):
        now=datetime(2026,11,18,11,30,tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(notification_market_date(now,{"market_date":"2026-11-17"},"workflow_dispatch"),"2026-11-17")
    def test_scheduled_run_uses_completed_session_date_at_ten_am(self):
        now=datetime(2026,11,18,10,0,tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(notification_market_date(now,{"market_date":"2026-11-17"},"schedule"),"2026-11-17")

    def test_scheduled_run_uses_current_session_after_close(self):
        now=datetime(2026,11,18,15,35,tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(notification_market_date(now,{"market_date":"2026-11-18"},"schedule"),"2026-11-18")
    def test_manual_run_bypasses_daily_dedupe(self):
        with tempfile.TemporaryDirectory() as d:
            record_notification_sent("2026-11-18",3,d)
            self.assertFalse(should_skip_duplicate("workflow_dispatch","2026-11-18",d))
            self.assertTrue(should_skip_duplicate("schedule","2026-11-18",d))
    def test_recovery_dispatch_uses_current_date_and_daily_dedupe(self):
        now=datetime(2026,11,23,15,55,tzinfo=ZoneInfo("Asia/Shanghai")); marker="recovery:20261120-1535"
        self.assertTrue(is_recovery_dispatch("workflow_dispatch",marker))
        self.assertEqual(notification_market_date(now,{"market_date":"2026-11-20"},"workflow_dispatch",marker),"2026-11-20")
        self.assertEqual(notification_market_date(now,{"market_date":"2026-11-19"},"workflow_dispatch",marker),"2026-11-19")
        with tempfile.TemporaryDirectory() as d:
            record_notification_sent("2026-11-18",3,d)
            self.assertTrue(should_skip_duplicate("workflow_dispatch","2026-11-18",d,marker))
    def test_manual_run_is_not_misclassified_as_recovery(self):
        self.assertFalse(is_recovery_dispatch("workflow_dispatch",""))
        self.assertFalse(is_recovery_dispatch("schedule","recovery:20261118-1535"))
    def test_signal_rows_must_match_latest_completed_session(self):
        rows=[{"name":"示例股票","confirmation_date":"2026-11-17"}]
        self.assertEqual(validate_signal_rows(rows,"2026-11-17"),rows)
        with self.assertRaises(RuntimeError): validate_signal_rows(rows,"2026-11-18")
    def test_manual_run_requires_market_date(self):
        now=datetime(2026,11,18,11,30,tzinfo=ZoneInfo("Asia/Shanghai"))
        with self.assertRaises(RuntimeError): notification_market_date(now,{},"workflow_dispatch")
    def test_manual_run_can_push_completed_session_on_weekend(self):
        self.assertFalse(should_skip_non_trading_day(manual=True,is_trading_day=False))
    def test_automatic_scheduled_and_recovery_runs_still_skip_weekends(self):
        self.assertTrue(should_skip_non_trading_day(manual=False,is_trading_day=False))
    def test_automatic_runs_continue_on_trading_days(self):
        self.assertFalse(should_skip_non_trading_day(manual=False,is_trading_day=True))
if __name__=="__main__": unittest.main()
