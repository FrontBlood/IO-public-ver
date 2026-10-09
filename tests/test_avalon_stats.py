import sqlite3
import unittest
from unittest.mock import patch

from database import avalon_db
from services import avalon_rules as rules
from services.avalon_stats import build_player_stats_embed


def finished_state(game_id, winner, win_code):
    return {
        "id": game_id,
        "status": "FINISHED",
        "winner": winner,
        "win_code": win_code,
        "finished_at": "2026-06-30T00:00:00+00:00",
        "players": [{"id": str(index)} for index in range(1, 6)],
        "roles": {
            "1": rules.MERLIN,
            "2": rules.PERCIVAL,
            "3": rules.LOYAL_SERVANT,
            "4": rules.ASSASSIN,
            "5": rules.MORGANA,
        },
    }


class AvalonStatsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.connect_patch = patch.object(avalon_db, "_connect", return_value=self.conn)
        self.connect_patch.start()

    def tearDown(self):
        self.connect_patch.stop()
        self.conn.close()

    def test_results_are_idempotent_and_special_stats_are_precise(self):
        good_game = finished_state(1, rules.GOOD, "ASSASSIN_MISSED")
        evil_game = finished_state(2, rules.EVIL, "ASSASSIN_HIT")
        self.assertEqual(5, avalon_db.record_game_results(good_game))
        self.assertEqual(0, avalon_db.record_game_results(good_game))
        self.assertEqual(5, avalon_db.record_game_results(evil_game))

        merlin = avalon_db.get_player_stats("1")
        assassin = avalon_db.get_player_stats("4")
        self.assertEqual((2, 1, 50.0), (merlin["total_games"], merlin["wins"], merlin["win_rate"]))
        self.assertEqual(1, merlin["merlin_survived_wins"])
        self.assertEqual(1, assassin["assassin_hits"])

    def test_leaderboard_supports_three_metrics(self):
        for game_id in range(1, 4):
            avalon_db.record_game_results(
                finished_state(game_id, rules.GOOD, "ASSASSIN_MISSED")
            )
        for metric in ("wins", "win_rate", "games"):
            rows = avalon_db.get_leaderboard(metric)
            self.assertEqual(5, len(rows))
            self.assertIn("win_rate", rows[0])

    def test_leaderboard_requires_three_completed_games(self):
        for game_id in range(1, 3):
            avalon_db.record_game_results(
                finished_state(game_id, rules.GOOD, "ASSASSIN_MISSED")
            )
        self.assertEqual([], avalon_db.get_leaderboard("wins"))

        avalon_db.record_game_results(
            finished_state(3, rules.EVIL, "ASSASSIN_HIT")
        )
        self.assertEqual(5, len(avalon_db.get_leaderboard("wins")))

    def test_stats_embed_uses_balanced_four_character_labels(self):
        embed = build_player_stats_embed(
            "1",
            "玩家一",
            {
                "wins": 3,
                "win_rate": 60.0,
                "total_games": 5,
                "merlin_survived_wins": 1,
                "assassin_hits": 2,
            },
        )
        names = {field.name for field in embed.fields}
        self.assertIn("梅林胜活", names)
        self.assertIn("刺客刺胜", names)


if __name__ == "__main__":
    unittest.main()
