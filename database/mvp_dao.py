import sqlite3
import json
import os

DB_PATH = "mvp.db"


# ============================
# 初始化表
# ============================
def init_mvp_tables():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # 状态表
        c.execute("""
            CREATE TABLE IF NOT EXISTS mvp_state (
                id INTEGER PRIMARY KEY,
                message_id TEXT,
                channel_id TEXT,
                is_open INTEGER,
                candidates TEXT
            )
        """)

        # 投票表
        c.execute("""
            CREATE TABLE IF NOT EXISTS mvp_votes (
                user_id TEXT PRIMARY KEY,
                candidate_id TEXT
            )
        """)

        conn.commit()


# ============================
# 保存状态
# ============================
def save_mvp_state(message_id, channel_id, candidates):
    init_mvp_tables()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("DELETE FROM mvp_state")

        c.execute("""
            INSERT INTO mvp_state (id, message_id, channel_id, is_open, candidates)
            VALUES (1, ?, ?, 1, ?)
        """, (message_id, channel_id, json.dumps(candidates)))

        conn.commit()


# ============================
# 获取状态
# ============================
def get_mvp_state():
    init_mvp_tables()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        row = c.execute("SELECT message_id, channel_id, is_open, candidates FROM mvp_state WHERE id=1").fetchone()

        if not row:
            return None

        message_id, channel_id, is_open, candidates_json = row

        return {
            "message_id": message_id,
            "channel_id": channel_id,
            "is_open": bool(is_open),
            "candidates": json.loads(candidates_json)
        }


# ============================
# 关闭投票
# ============================
def close_mvp_state():
    init_mvp_tables()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE mvp_state SET is_open = 0 WHERE id=1")
        conn.commit()


# ============================
# 清空投票
# ============================
def clear_votes():
    init_mvp_tables()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM mvp_votes")
        conn.commit()


# ============================
# 加票 / 覆盖投票
# ============================
def add_vote(user_id, candidate_id):
    init_mvp_tables()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("REPLACE INTO mvp_votes (user_id, candidate_id) VALUES (?, ?)",
                  (user_id, candidate_id))

        conn.commit()


# ============================
# 获取投票
# 返回：[(user_id, candidate_id), ...]
# ============================
def get_votes():
    init_mvp_tables()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        rows = c.execute("SELECT user_id, candidate_id FROM mvp_votes").fetchall()
        return rows


# ============================
# 获取唯一投票者
# ============================
def get_unique_voters():
    init_mvp_tables()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        rows = c.execute("SELECT user_id FROM mvp_votes").fetchall()
        return [r[0] for r in rows]
