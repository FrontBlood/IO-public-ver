import sqlite3
import unittest
import uuid
from datetime import date
from pathlib import Path

from tools.user_activity_report import build_report


class UserActivityReportTest(unittest.TestCase):
    def test_weekly_activity_and_retention(self):
        db = Path(__file__).parent / f".user_activity_{uuid.uuid4().hex}.db"
        try:
            conn = sqlite3.connect(db)
            try:
                conn.execute("CREATE TABLE user_xp (user_id TEXT PRIMARY KEY)")
                conn.executemany("INSERT INTO user_xp VALUES (?)", [("a",), ("b",), ("c",)])
                conn.execute("CREATE TABLE daily_xp_log (user_id TEXT, xp_type TEXT, date TEXT, amount INTEGER)")
                conn.executemany(
                    "INSERT INTO daily_xp_log VALUES (?, ?, ?, ?)",
                    [
                        ("a", "text", "2026-01-05", 10),
                        ("b", "voice", "2026-01-11", 20),
                        ("a", "text", "2026-01-12", 10),
                        ("c", "stream", "2026-01-18", 30),
                    ],
                )
                conn.commit()
            finally:
                conn.close()
            report = build_report(db, end=date(2026, 1, 18))
            self.assertEqual(report["current"]["wau"], 2)
            self.assertEqual(report["previous"]["wau"], 2)
            self.assertEqual(report["retention"]["retained_users"], 1)
            self.assertEqual(report["retention"]["week_over_week_retention"], 0.5)
            self.assertEqual(report["retention"]["new_active_users"], 1)
        finally:
            db.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
