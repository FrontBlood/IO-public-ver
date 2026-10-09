import sqlite3
from datetime import datetime
from config.constants import TEMP_PATH  # 数据库路径仍保留集中定义

def init_temp_role_table():
    with sqlite3.connect(TEMP_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS temporary_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                user_id TEXT,
                role_id TEXT,
                expire_at TEXT
            )
        ''')
        conn.commit()

def add_temp_role(guild_id: int, user_id: int, role_id: int, expire_at: datetime):
    with sqlite3.connect(TEMP_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO temporary_roles (guild_id, user_id, role_id, expire_at)
            VALUES (?, ?, ?, ?)
        """, (str(guild_id), str(user_id), str(role_id), expire_at.isoformat()))
        conn.commit()

def remove_temp_role(user_id: int, role_id: int):
    with sqlite3.connect(TEMP_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM temporary_roles WHERE user_id = ? AND role_id = ?", (str(user_id), str(role_id)))
        conn.commit()

def get_temp_roles(user_id: int):
    with sqlite3.connect(TEMP_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT role_id, expire_at FROM temporary_roles WHERE user_id = ?", (str(user_id),))
        return c.fetchall()

def get_temp_roles_due(current_time: datetime):
    with sqlite3.connect(TEMP_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, guild_id, user_id, role_id, expire_at FROM temporary_roles")
        rows = c.fetchall()
        return [
            (id_, guild_id, user_id, role_id, expire_at)
            for (id_, guild_id, user_id, role_id, expire_at) in rows
            if datetime.fromisoformat(expire_at) <= current_time
        ]

def remove_temp_role_entry(entry_id: int):
    with sqlite3.connect(TEMP_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM temporary_roles WHERE id = ?", (entry_id,))
        conn.commit()
