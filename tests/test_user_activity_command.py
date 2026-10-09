import unittest

from commands.user_activity_report import _change, build_weekly_embed


class UserActivityCommandTest(unittest.TestCase):
    def test_change_format(self):
        self.assertEqual(_change(-0.1777), "↓ 17.8%")
        self.assertEqual(_change(0.1), "↑ 10.0%")

    def test_embed_contains_core_metrics(self):
        report = {
            "current": {"start": "2026-05-12", "end": "2026-05-18", "wau": 310, "avg_dau": 156.0, "peak_dau": 187, "stickiness": 0.5032, "total_xp": 1000, "channel_users": {"text": 10, "voice": 20, "stream": 3}, "channel_xp": {"text": 100, "voice": 800, "stream": 100}},
            "previous": {"start": "2026-05-05", "end": "2026-05-11"},
            "comparison": {"wau": {"change_rate": -0.1777}, "avg_dau": {"change_rate": -0.1191}, "total_xp": {"change_rate": -0.1}},
            "retention": {"week_over_week_retention": 0.5995, "retained_users": 226, "new_active_users": 18, "resurrected_users": 66, "churned_users": 151},
            "source_coverage": {"first": "2025-04-24", "latest": "2026-05-19"},
            "excluded_partial_day": "2026-05-19",
        }
        payload = build_weekly_embed(report).to_dict()
        self.assertIn("310", payload["fields"][0]["value"])
        self.assertIn("60.0%", payload["fields"][1]["value"])
        self.assertIn("已排除", payload["footer"]["text"])


if __name__ == "__main__":
    unittest.main()
