from __future__ import annotations
import sys,unittest
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.cn_watchdog import recovery_is_due,recovery_marker
TZ=ZoneInfo("Asia/Shanghai")
class CNWatchdogScheduleTests(unittest.TestCase):
    def test_recovery_starts_at_1550_china_time(self):
        self.assertFalse(recovery_is_due(datetime(2026,11,23,15,49,tzinfo=TZ)))
        self.assertTrue(recovery_is_due(datetime(2026,11,23,15,50,tzinfo=TZ)))
    def test_recovery_does_not_run_on_weekends(self):
        self.assertFalse(recovery_is_due(datetime(2026,11,22,16,0,tzinfo=TZ)))
    def test_recovery_marker_is_unique_per_session(self):
        self.assertEqual(recovery_marker(date(2026,11,23)),"recovery:20261123-1535")
if __name__=="__main__": unittest.main()
