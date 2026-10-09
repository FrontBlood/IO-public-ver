# database/mengmeng_dao.py
import sqlite3
from datetime import datetime
from config.mengmeng_config import MENGMENG_DB_PATH

def _now():
    return datetime.utcnow().isoformat()

def init_mengmeng_tables():
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()

        # 余额账户
        c.execute("""
        CREATE TABLE IF NOT EXISTS mm_coin_account (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # 奖励去重与语音奖励节流
        c.execute("""
        CREATE TABLE IF NOT EXISTS mm_reward_flags (
            user_id TEXT PRIMARY KEY,
            gave_initial INTEGER NOT NULL DEFAULT 0,
            gave_checkin_7d INTEGER NOT NULL DEFAULT 0,
            gave_level_5 INTEGER NOT NULL DEFAULT 0,
            voice_week_start TEXT NOT NULL DEFAULT '',
            voice_week_count INTEGER NOT NULL DEFAULT 0,
            voice_day TEXT NOT NULL DEFAULT ''
        )
        """)

        # 每日感谢用量
        c.execute("""
        CREATE TABLE IF NOT EXISTS mm_thanks_daily (
            user_id TEXT NOT NULL,
            day TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day)
        )
        """)

        # ✅ 迎新陪伴累计（按语音频道维度）
        c.execute("""
        CREATE TABLE IF NOT EXISTS mm_welcome_time_vc (
            vc_id TEXT NOT NULL,
            mentor_user_id TEXT NOT NULL,
            total_seconds INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (vc_id, mentor_user_id)
        )
        """)

        # 流水（可审计）
        c.execute("""
        CREATE TABLE IF NOT EXISTS mm_tx_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            from_user TEXT,
            to_user TEXT,
            delta INTEGER NOT NULL,
            reason TEXT NOT NULL
        )
        """)

        conn.commit()

def ensure_user(user_id: str):
    now = _now()
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO mm_coin_account (user_id, balance, created_at, updated_at)
            VALUES (?, 0, ?, ?)
        """, (user_id, now, now))
        c.execute("""
            INSERT OR IGNORE INTO mm_reward_flags (user_id)
            VALUES (?)
        """, (user_id,))
        conn.commit()

def get_balance(user_id: str) -> int:
    ensure_user(user_id)
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT balance FROM mm_coin_account WHERE user_id=?", (user_id,))
        row = c.fetchone()
        return int(row[0]) if row else 0

def add_balance(user_id: str, delta: int, reason: str, from_user: str = None, to_user: str = None):
    ensure_user(user_id)
    now = _now()
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE mm_coin_account
            SET balance = balance + ?, updated_at=?
            WHERE user_id=?
        """, (delta, now, user_id))
        c.execute("""
            INSERT INTO mm_tx_log (ts, from_user, to_user, delta, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (now, from_user, to_user, delta, reason))
        conn.commit()

def get_flags(user_id: str):
    ensure_user(user_id)
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT gave_initial, gave_checkin_7d, gave_level_5, voice_week_start, voice_week_count, voice_day
            FROM mm_reward_flags
            WHERE user_id=?
        """, (user_id,))
        return c.fetchone()

def set_flag(user_id: str, field: str, value: int):
    ensure_user(user_id)
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE mm_reward_flags SET {field}=? WHERE user_id=?", (value, user_id))
        conn.commit()

def set_voice_week(user_id: str, week_start: str, count: int):
    ensure_user(user_id)
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE mm_reward_flags
            SET voice_week_start=?, voice_week_count=?
            WHERE user_id=?
        """, (week_start, count, user_id))
        conn.commit()

def set_voice_day(user_id: str, day_s: str):
    ensure_user(user_id)
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("UPDATE mm_reward_flags SET voice_day=? WHERE user_id=?", (day_s, user_id))
        conn.commit()

def get_thanks_used(user_id: str, day_s: str) -> int:
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT used FROM mm_thanks_daily WHERE user_id=? AND day=?", (user_id, day_s))
        row = c.fetchone()
        return int(row[0]) if row else 0

def inc_thanks_used(user_id: str, day_s: str, inc: int = 1):
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO mm_thanks_daily (user_id, day, used)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, day) DO UPDATE SET used = used + excluded.used
        """, (user_id, day_s, inc))
        conn.commit()

# ==========================
# ✅ 迎新陪伴：按语音频道维度
# ==========================
def add_welcome_seconds_vc(vc_id: str, mentor_user_id: str, seconds: int):
    now = _now()
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO mm_welcome_time_vc (vc_id, mentor_user_id, total_seconds, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(vc_id, mentor_user_id) DO UPDATE SET
                total_seconds = total_seconds + excluded.total_seconds,
                updated_at = excluded.updated_at
        """, (vc_id, mentor_user_id, seconds, now))
        conn.commit()

def top_welcome_in_vc(vc_id: str, limit: int = 5):
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT mentor_user_id, total_seconds
            FROM mm_welcome_time_vc
            WHERE vc_id=?
            ORDER BY total_seconds DESC
            LIMIT ?
        """, (vc_id, limit))
        rows = c.fetchall()
        return [(r[0], int(r[1])) for r in rows]

def sum_welcome_seconds_all() -> int:
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(total_seconds), 0) FROM mm_welcome_time_vc")
        row = c.fetchone()
        return int(row[0]) if row else 0

def get_welcome_seconds_vc(vc_id: str, mentor_user_id: str) -> int:
    """返回该迎新在指定语音频道(vc)的累计陪伴秒数。"""
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT total_seconds
            FROM mm_welcome_time_vc
            WHERE vc_id=? AND mentor_user_id=?
        """, (vc_id, mentor_user_id))
        row = c.fetchone()
        return int(row[0]) if row else 0


def get_welcome_rank_vc(vc_id: str, mentor_user_id: str):
    """返回该迎新在指定语音频道(vc)的排名（从1开始）。若无记录返回 None。"""
    my_sec = get_welcome_seconds_vc(vc_id, mentor_user_id)
    if my_sec <= 0:
        return None
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        # 排名 = 比我秒数更高的人数 + 1
        c.execute("""
            SELECT COUNT(*)
            FROM mm_welcome_time_vc
            WHERE vc_id=? AND total_seconds > ?
        """, (vc_id, my_sec))
        row = c.fetchone()
        higher = int(row[0]) if row else 0
        return higher + 1


def sum_welcome_seconds_for_user(mentor_user_id: str) -> int:
    """该迎新在所有语音频道的陪伴总秒数。"""
    with sqlite3.connect(MENGMENG_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT COALESCE(SUM(total_seconds), 0)
            FROM mm_welcome_time_vc
            WHERE mentor_user_id=?
        """, (mentor_user_id,))
        row = c.fetchone()
        return int(row[0]) if row else 0
