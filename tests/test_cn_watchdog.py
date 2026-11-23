import unittest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from scripts import cn_watchdog

TZ = ZoneInfo("Asia/Shanghai")


def is_trading_day(day):
    return day.weekday() < 5


def previous_trading_day(day):
    candidate = day - timedelta(days=1)
    while not is_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


class CNWatchdogScheduleTests(unittest.TestCase):
    def test_scan_due_time_is_1000_china_time(self):
        self.assertEqual(cn_watchdog.DUE, time(10, 0))
        self.assertEqual(cn_watchdog.GRACE_MINUTES, 15)

    def test_recovery_grace_ends_at_1015(self):
        before = datetime(2026, 11, 23, 10, 14, tzinfo=TZ)
        due = datetime(2026, 11, 23, 10, 15, tzinfo=TZ)
        self.assertFalse(cn_watchdog.recovery_is_due(before))
        self.assertTrue(cn_watchdog.recovery_is_due(due))

    def test_session_resolution_uses_previous_completed_session_before_grace(self):
        current = datetime(2026, 11, 23, 10, 14, tzinfo=TZ)
        self.assertEqual(
            cn_watchdog.recovery_session_day(current, is_trading_day, previous_trading_day),
            date(2026, 11, 20),
        )

    def test_session_resolution_switches_to_today_after_grace(self):
        current = datetime(2026, 11, 23, 10, 15, tzinfo=TZ)
        self.assertEqual(
            cn_watchdog.recovery_session_day(current, is_trading_day, previous_trading_day),
            date(2026, 11, 23),
        )

    def test_recovery_window_tracks_ten_am_scan(self):
        start, end = cn_watchdog.recovery_run_window(date(2026, 11, 23))
        self.assertEqual(start, datetime(2026, 11, 23, 9, 45, tzinfo=TZ))
        self.assertEqual(end, datetime(2026, 11, 24, 9, 45, tzinfo=TZ))

    def test_recovery_marker_uses_ten_am_slot(self):
        self.assertEqual(cn_watchdog.recovery_marker(date(2026, 11, 23)), "recovery:20261123-1000")


if __name__ == "__main__":
    unittest.main()
