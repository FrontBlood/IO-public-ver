import sqlite3
import unittest
from unittest.mock import patch

from database import avalon_db


class AvalonDatabaseTests(unittest.TestCase):
    def test_game_lifecycle_and_active_channel_lookup(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            with patch.object(avalon_db, "_connect", return_value=conn):
                state = {
                    "guild_id": "1",
                    "channel_id": "2",
                    "message_id": "3",
                    "owner_id": "4",
                    "status": "LOBBY",
                    "players": [],
                }
                state = avalon_db.create_game(state)
                self.assertEqual(state["id"], avalon_db.get_game(state["id"])["id"])
                self.assertEqual(state["id"], avalon_db.get_game_by_message("3")["id"])
                self.assertEqual(state["id"], avalon_db.get_active_game_for_channel("2")["id"])

                state["status"] = "CANCELLED"
                avalon_db.save_game(state)
                self.assertIsNone(avalon_db.get_active_game_for_channel("2"))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
