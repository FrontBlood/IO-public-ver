# === checkin_database.py ===
import sqlite3
import os
from datetime import datetime, timezone
from config.constants import CHECKIN_DB_PATH

def init_checkin_db():
    with sqlite3.connect(CHECKIN_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        # 创建表（若不存在）
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_checkin (
                user_id TEXT PRIMARY KEY,
                last_checkin TEXT,
                streak INTEGER DEFAULT 1
            )
        ''')
        # 检查并添加 max_streak 字段（用于旧数据库迁移）
        c.execute("PRAGMA table_info(user_checkin)")
        columns = [col[1] for col in c.fetchall()]
        if "max_streak" not in columns:
            c.execute("ALTER TABLE user_checkin ADD COLUMN max_streak INTEGER DEFAULT 1")
            # 同步初始化为 streak 值（已存在的用户）
            c.execute("UPDATE user_checkin SET max_streak = streak")
        conn.commit()

def get_checkin_data(user_id: str):
    conn = sqlite3.connect(CHECKIN_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT last_checkin, streak, max_streak FROM user_checkin WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_checkin_data(user_id: str, timestamp: str, streak: int, max_streak: int):
    conn = sqlite3.connect(CHECKIN_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE user_checkin SET last_checkin = ?, streak = ?, max_streak = ? WHERE user_id = ?",
              (timestamp, streak, max_streak, user_id))
    conn.commit()
    conn.close()

def insert_checkin_data(user_id: str, timestamp: str):
    conn = sqlite3.connect(CHECKIN_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO user_checkin (user_id, last_checkin, streak, max_streak) VALUES (?, ?, ?, ?)",
              (user_id, timestamp, 1, 1))
    conn.commit()
    conn.close()

def get_streak(user_id: str) -> int:
    conn = sqlite3.connect(CHECKIN_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT streak FROM user_checkin WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_max_streak(user_id: str) -> int:
    conn = sqlite3.connect(CHECKIN_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT max_streak FROM user_checkin WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_top_checkins(limit=10):
    with sqlite3.connect(CHECKIN_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, streak FROM user_checkin ORDER BY streak DESC LIMIT ?", (limit,))
        return c.fetchall()

def get_top_max_checkins(limit=10):
    with sqlite3.connect(CHECKIN_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, max_streak FROM user_checkin ORDER BY max_streak DESC LIMIT ?", (limit,))
        return c.fetchall()

def get_user_checkin_rank(user_id):
    with sqlite3.connect(CHECKIN_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT COUNT(*) + 1 FROM user_checkin
            WHERE streak > (SELECT streak FROM user_checkin WHERE user_id = ?)
        """, (user_id,))
        row = c.fetchone()
        return row[0] if row else None
