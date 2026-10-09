import sqlite3
from datetime import datetime
from config.constants import CURRENCY_DB_PATH

def init_drop_log():
    with sqlite3.connect(CURRENCY_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS drop_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                amount INTEGER,
                timestamp TEXT
            )
        ''')
        conn.commit()

def log_drop(user_id, amount):
    with sqlite3.connect(CURRENCY_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO drop_log (user_id, amount, timestamp) VALUES (?, ?, ?)",
                  (user_id, amount, datetime.utcnow().isoformat()))
        conn.commit()

def get_total_drops():
    with sqlite3.connect(CURRENCY_DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT SUM(amount) FROM drop_log")
        row = c.fetchone()
        return row[0] or 0
