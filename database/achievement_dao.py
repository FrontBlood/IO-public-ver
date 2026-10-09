# database/achievement_dao.py

import sqlite3
from config.constants import DB_PATH

def init_achievement_table():
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id TEXT,
                achievement_id TEXT,
                unlocked_at TEXT,
                PRIMARY KEY (user_id, achievement_id)
            )
        ''')
        conn.commit()

def is_unlocked(user_id: str, achievement_id: str) -> bool:
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = ?", (user_id, achievement_id))
        return c.fetchone() is not None

def unlock_achievement(user_id: str, achievement_id: str):
    from datetime import datetime, timezone
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO user_achievements (user_id, achievement_id, unlocked_at)
            VALUES (?, ?, ?)
        """, (user_id, achievement_id, datetime.now(timezone.utc).isoformat()))
        conn.commit()

def get_unlocked_achievement_ids(user_id: str):
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT achievement_id FROM user_achievements WHERE user_id = ?", (user_id,))
        return [row[0] for row in c.fetchall()]

def reset_user_achievements(user_id: str):
    """
    删除用户的所有成就记录（等价于重置为未解锁）
    """
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM user_achievements WHERE user_id = ?", (user_id,))
        conn.commit()

def clear_user_achievements(user_id: str):
    """
    删除用户的所有成就记录（命名语义强调彻底清除）
    """
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM user_achievements WHERE user_id = ?", (user_id,))
        conn.commit()

# 工具函数：生成字符型进度条（如 ███░░░░░░）
def generate_progress_bar(current, total, length=20):
    filled = min(length, int(length * current / total)) if total else 0
    empty = length - filled
    bar = '█' * filled + ' ' * empty
    percent_value = min(100.0, (current / total) * 100) if total else 0.0
    percent = f"{percent_value:.2f}%"
    return f"`{bar}`", percent
