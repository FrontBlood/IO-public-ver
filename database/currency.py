# database/currency_system.py

import sqlite3
from config.constants import CURRENCY_DB_PATH, CURRENCY_NAME

# === 初始化货币数据库表 ===
def init_currency_db():
    with sqlite3.connect(CURRENCY_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_currency (
                user_id TEXT PRIMARY KEY,
                amount REAL DEFAULT 0
            )
        """)
        conn.commit()

# === 获取玩家余额 ===
def get_balance(user_id):
    with sqlite3.connect(CURRENCY_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT amount FROM user_currency WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            return row[0]
        else:
            return 0

# === 增加货币 ===
def add_balance(user_id, amount):
    with sqlite3.connect(CURRENCY_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO user_currency (user_id, amount) VALUES (?, 0)", (user_id,))
        c.execute("UPDATE user_currency SET amount = amount + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

# === 扣除货币 ===
def subtract_balance(user_id, amount):
    with sqlite3.connect(CURRENCY_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        current = get_balance(user_id)
        if current < amount:
            raise ValueError(f"余额不足，无法扣除 {amount} {CURRENCY_NAME}")
        c.execute("UPDATE user_currency SET amount = amount - ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
