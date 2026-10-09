import sqlite3
import unittest
from unittest.mock import patch

from database import avalon_db


class AvalonMultiInstanceTests(unittest.TestCase):
    def test_same_server_can_run_independent_games_in_different_channels(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            with patch.object(avalon_db, "_connect", return_value=conn):
                first = avalon_db.create_game(
                    {
                        "guild_id": "1",
                        "channel_id": "100",
                        "message_id": "1000",
                        "owner_id": "10",
                        "status": "LOBBY",
                        "players": [],
                    }
                )
                second = avalon_db.create_game(
                    {
                        "guild_id": "1",
                        "channel_id": "200",
                        "message_id": "2000",
                        "owner_id": "20",
                        "status": "LOBBY",
                        "players": [],
                    }
                )

                self.assertNotEqual(first["id"], second["id"])
                self.assertEqual(first["id"], avalon_db.get_active_game_for_channel("100")["id"])
                self.assertEqual(second["id"], avalon_db.get_active_game_for_channel("200")["id"])
                self.assertEqual(2, len(avalon_db.list_active_games()))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
