# arena_dao.py

import sqlite3
from config.constants import ARENA_DB_PATH


def init_arena_table():
    with sqlite3.connect(ARENA_DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS arena_stats (
                user_id TEXT PRIMARY KEY,
                total_matches INTEGER DEFAULT 0,
                total_wins INTEGER DEFAULT 0,
                defender_wins INTEGER DEFAULT 0,
                challenger_wins INTEGER DEFAULT 0,
                defends_success INTEGER DEFAULT 0
            )
        ''')
        conn.commit()


def record_victory(user_id: int, is_defender: bool = False, defended: bool = False):
    with sqlite3.connect(ARENA_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO arena_stats (user_id, total_matches, total_wins, defender_wins, challenger_wins, defends_success)
            VALUES (?, 1, 1, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                total_matches = total_matches + 1,
                total_wins = total_wins + 1,
                defender_wins = defender_wins + excluded.defender_wins,
                challenger_wins = challenger_wins + excluded.challenger_wins,
                defends_success = defends_success + excluded.defends_success
        """, (
            str(user_id),
            1 if is_defender else 0,
            1 if not is_defender else 0,
            1 if defended else 0
        ))


def get_user_stats(user_id: str):
    with sqlite3.connect(ARENA_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT total_matches, total_wins, defender_wins, challenger_wins, defends_success FROM arena_stats WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            return None
        return {
            "total_matches": row[0],
            "total_wins": row[1],
            "defender_wins": row[2],
            "challenger_wins": row[3],
            "defends_success": row[4]
        }
