import sqlite3
from datetime import datetime, timezone

from config.constants import CHECKIN_EVENT_DB_PATH


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect():
    conn = sqlite3.connect(CHECKIN_EVENT_DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_checkin_event_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkin_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                reward_limit INTEGER NOT NULL,
                required_streak INTEGER NOT NULL,
                announce_channel_id TEXT NOT NULL,
                announce_message_id TEXT,
                redeem_channel_id TEXT NOT NULL,
                admin_user_id TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'normal'
            )
            """
        )
        event_columns = [row["name"] for row in conn.execute("PRAGMA table_info(checkin_events)").fetchall()]
        if "mode" not in event_columns:
            conn.execute("ALTER TABLE checkin_events ADD COLUMN mode TEXT NOT NULL DEFAULT 'normal'")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkin_event_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                achieved_at TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                code_sent_at TEXT,
                code_send_error TEXT,
                redeemed_at TEXT,
                redeem_channel_id TEXT,
                redeem_message_id TEXT,
                admin_message_id TEXT,
                settled_at TEXT,
                settled_by TEXT,
                status TEXT NOT NULL,
                UNIQUE(event_id, user_id),
                FOREIGN KEY(event_id) REFERENCES checkin_events(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_checkin_event_rewards_event ON checkin_event_rewards(event_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_checkin_event_rewards_code ON checkin_event_rewards(code)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_checkin_event_rewards_admin_message "
            "ON checkin_event_rewards(admin_message_id)"
        )
        conn.commit()


def get_current_event() -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM checkin_events
            WHERE status IN ('scheduled', 'active')
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()


def get_latest_normal_event() -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM checkin_events
            WHERE mode = 'normal'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()


def create_event(
    created_by: str,
    start_at: str,
    end_at: str,
    reward_limit: int,
    required_streak: int,
    announce_channel_id: str,
    redeem_channel_id: str,
    admin_user_id: str,
    mode: str = "normal",
) -> sqlite3.Row:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO checkin_events
            (status, created_at, created_by, start_at, end_at, reward_limit, required_streak,
             announce_channel_id, redeem_channel_id, admin_user_id, mode)
            VALUES ('scheduled', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now_iso(),
                created_by,
                start_at,
                end_at,
                reward_limit,
                required_streak,
                announce_channel_id,
                redeem_channel_id,
                admin_user_id,
                mode,
            ),
        )
        conn.commit()
        return conn.execute("SELECT * FROM checkin_events WHERE id = ?", (cur.lastrowid,)).fetchone()


def get_event(event_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM checkin_events WHERE id = ?", (event_id,)).fetchone()


def update_event_status(event_id: int, status: str):
    with connect() as conn:
        conn.execute("UPDATE checkin_events SET status = ? WHERE id = ?", (status, event_id))
        conn.commit()


def update_event_end(event_id: int, end_at: str, status: str | None = None):
    with connect() as conn:
        if status is None:
            conn.execute("UPDATE checkin_events SET end_at = ? WHERE id = ?", (end_at, event_id))
        else:
            conn.execute(
                "UPDATE checkin_events SET end_at = ?, status = ? WHERE id = ?",
                (end_at, status, event_id),
            )
        conn.commit()


def update_announce_message(event_id: int, message_id: str):
    with connect() as conn:
        conn.execute(
            "UPDATE checkin_events SET announce_message_id = ? WHERE id = ?",
            (message_id, event_id),
        )
        conn.commit()


def delete_event(event_id: int):
    with connect() as conn:
        conn.execute("DELETE FROM checkin_event_rewards WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM checkin_events WHERE id = ?", (event_id,))
        conn.commit()


def count_rewards(event_id: int) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM checkin_event_rewards WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        return int(row["count"] if row else 0)


def get_reward_by_user(event_id: int, user_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM checkin_event_rewards WHERE event_id = ? AND user_id = ?",
            (event_id, user_id),
        ).fetchone()


def code_exists(code: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM checkin_event_rewards WHERE code = ? LIMIT 1",
            (code,),
        ).fetchone()
        return bool(row)


def add_reward(event_id: int, user_id: str, achieved_at: str, code: str) -> sqlite3.Row | None:
    with connect() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO checkin_event_rewards
                (event_id, user_id, achieved_at, code, status)
                VALUES (?, ?, ?, ?, 'awarded')
                """,
                (event_id, user_id, achieved_at, code),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return None
        return conn.execute("SELECT * FROM checkin_event_rewards WHERE id = ?", (cur.lastrowid,)).fetchone()


def list_unsent_rewards(event_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT * FROM checkin_event_rewards
            WHERE event_id = ? AND code_sent_at IS NULL AND code_send_error IS NULL
            ORDER BY id ASC
            """,
            (event_id,),
        ).fetchall()


def mark_code_sent(reward_id: int):
    with connect() as conn:
        conn.execute(
            "UPDATE checkin_event_rewards SET code_sent_at = ?, code_send_error = NULL WHERE id = ?",
            (utc_now_iso(), reward_id),
        )
        conn.commit()


def mark_code_send_error(reward_id: int, error: str):
    with connect() as conn:
        conn.execute(
            "UPDATE checkin_event_rewards SET code_send_error = ? WHERE id = ?",
            (error[:500], reward_id),
        )
        conn.commit()


def get_reward_by_code(code: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM checkin_event_rewards WHERE code = ?",
            (code.upper(),),
        ).fetchone()


def mark_redeemed(reward_id: int, channel_id: str, message_id: str):
    with connect() as conn:
        conn.execute(
            """
            UPDATE checkin_event_rewards
            SET status = 'redeemed', redeemed_at = ?, redeem_channel_id = ?, redeem_message_id = ?
            WHERE id = ? AND settled_at IS NULL
            """,
            (utc_now_iso(), channel_id, message_id, reward_id),
        )
        conn.commit()


def update_admin_message(reward_id: int, admin_message_id: str):
    with connect() as conn:
        conn.execute(
            "UPDATE checkin_event_rewards SET admin_message_id = ? WHERE id = ?",
            (admin_message_id, reward_id),
        )
        conn.commit()


def get_reward_by_admin_message(message_id: str) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM checkin_event_rewards WHERE admin_message_id = ?",
            (message_id,),
        ).fetchone()


def mark_settled(reward_id: int, settled_by: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE checkin_event_rewards
            SET status = 'settled', settled_at = ?, settled_by = ?
            WHERE id = ? AND settled_at IS NULL
            """,
            (utc_now_iso(), settled_by, reward_id),
        )
        conn.commit()
        return cur.rowcount > 0


def list_rewards(event_id: int) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM checkin_event_rewards WHERE event_id = ? ORDER BY id ASC",
            (event_id,),
        ).fetchall()
