import sqlite3
from datetime import datetime

from config.constants import PRIVATE_ROOM_DB_PATH


def init_private_room_table():
    with sqlite3.connect(PRIVATE_ROOM_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS private_room_state (
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                last_empty_at TEXT DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            )
            """
        )
        conn.commit()


def ensure_private_room_record(guild_id: int | str, channel_id: int | str):
    now_iso = datetime.utcnow().isoformat()
    with sqlite3.connect(PRIVATE_ROOM_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO private_room_state (guild_id, channel_id, last_empty_at, updated_at)
            VALUES (?, ?, '', ?)
            ON CONFLICT(guild_id, channel_id)
            DO UPDATE SET updated_at = excluded.updated_at
            """,
            (str(guild_id), str(channel_id), now_iso),
        )
        conn.commit()


def mark_private_room_empty(guild_id: int | str, channel_id: int | str, empty_at: datetime):
    empty_at_iso = empty_at.isoformat()
    with sqlite3.connect(PRIVATE_ROOM_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO private_room_state (guild_id, channel_id, last_empty_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, channel_id)
            DO UPDATE SET
                last_empty_at = excluded.last_empty_at,
                updated_at = excluded.updated_at
            """,
            (str(guild_id), str(channel_id), empty_at_iso, empty_at_iso),
        )
        conn.commit()


def clear_private_room_empty(guild_id: int | str, channel_id: int | str):
    now_iso = datetime.utcnow().isoformat()
    with sqlite3.connect(PRIVATE_ROOM_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO private_room_state (guild_id, channel_id, last_empty_at, updated_at)
            VALUES (?, ?, '', ?)
            ON CONFLICT(guild_id, channel_id)
            DO UPDATE SET
                last_empty_at = '',
                updated_at = excluded.updated_at
            """,
            (str(guild_id), str(channel_id), now_iso),
        )
        conn.commit()


def get_private_room_state(guild_id: int | str, channel_id: int | str) -> dict | None:
    with sqlite3.connect(PRIVATE_ROOM_DB_PATH, timeout=5.0) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT guild_id, channel_id, last_empty_at, updated_at
            FROM private_room_state
            WHERE guild_id = ? AND channel_id = ?
            """,
            (str(guild_id), str(channel_id)),
        )
        row = c.fetchone()
    return dict(row) if row else None
