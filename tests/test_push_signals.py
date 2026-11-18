from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from push_signals import (
    notification_market_date,
    record_notification_sent,
    should_skip_duplicate,
    validate_signal_rows,
)


class BarkNotificationPolicyTests(unittest.TestCase):
    def test_manual_run_uses_latest_completed_session_before_close(self):
        now = datetime(2026, 11, 18, 11, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        summary = {"market_date": "2026-11-17"}
        self.assertEqual(
            notification_market_date(now, summary, "workflow_dispatch"),
            "2026-11-17",
        )

    def test_scheduled_run_uses_current_session_date(self):
        now = datetime(2026, 11, 18, 15, 35, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(
            notification_market_date(now, {"market_date": "2026-11-18"}, "schedule"),
            "2026-11-18",
        )

    def test_manual_run_bypasses_daily_dedupe(self):
        with tempfile.TemporaryDirectory() as directory:
            record_notification_sent("2026-11-18", 3, directory)
            self.assertFalse(
                should_skip_duplicate("workflow_dispatch", "2026-11-18", directory)
            )
            self.assertTrue(
                should_skip_duplicate("schedule", "2026-11-18", directory)
            )

    def test_signal_rows_must_match_latest_completed_session(self):
        rows = [{"name": "示例股票", "confirmation_date": "2026-11-17"}]
        self.assertEqual(validate_signal_rows(rows, "2026-11-17"), rows)
        with self.assertRaises(RuntimeError):
            validate_signal_rows(rows, "2026-11-18")

    def test_manual_run_requires_market_date(self):
        now = datetime(2026, 11, 18, 11, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        with self.assertRaises(RuntimeError):
            notification_market_date(now, {}, "workflow_dispatch")


if __name__ == "__main__":
    unittest.main()
