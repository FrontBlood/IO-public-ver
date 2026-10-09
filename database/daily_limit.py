import sqlite3
from datetime import datetime, timezone

DB_PATH = "levels.db"

def can_gain_xp(user_id, xp_type, amount):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    LIMITS = {"text": 500, "voice": 1000, "stream": 2000}

    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_xp_log (
                user_id TEXT,
                xp_type TEXT,
                date TEXT,
                amount INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, xp_type, date)
            )
        """)

        c.execute("SELECT amount FROM daily_xp_log WHERE user_id = ? AND xp_type = ? AND date = ?",
                  (user_id, xp_type, today))
        row = c.fetchone()
        current = row[0] if row else 0

        if current + amount > LIMITS[xp_type]:
            return False

        if row:
            c.execute("UPDATE daily_xp_log SET amount = amount + ? WHERE user_id = ? AND xp_type = ? AND date = ?",
                      (amount, user_id, xp_type, today))
        else:
            c.execute("INSERT INTO daily_xp_log (user_id, xp_type, date, amount) VALUES (?, ?, ?, ?)",
                      (user_id, xp_type, today, amount))

        conn.commit()

    return True
