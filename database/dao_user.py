import sqlite3

DB_PATH = "levels.db"

class User:
    def __init__(self, user_id, text_xp, voice_xp, stream_xp, last_active_date):
        self.user_id = user_id
        self.text_xp = text_xp
        self.voice_xp = voice_xp
        self.stream_xp = stream_xp
        self.last_active_date = last_active_date

def get_or_create_user(user_id):
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_xp (
                user_id TEXT PRIMARY KEY,
                text_xp INTEGER DEFAULT 0,
                voice_xp INTEGER DEFAULT 0,
                stream_xp INTEGER DEFAULT 0,
                last_active_date TEXT DEFAULT ''
            )
        """)
        c.execute("SELECT * FROM user_xp WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO user_xp (user_id) VALUES (?)", (user_id,))
            conn.commit()
            row = (user_id, 0, 0, 0, '')
    return User(row[0], row[1], row[2], row[3], row[4])

def get_all_users():
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, text_xp, voice_xp, stream_xp, last_active_date FROM user_xp")
        rows = c.fetchall()
    users = [User(row[0], row[1], row[2], row[3], row[4]) for row in rows]
    return users

def update_user(user):
    with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE user_xp
            SET text_xp = ?, voice_xp = ?, stream_xp = ?, last_active_date = ?
            WHERE user_id = ?
        """, (user.text_xp, user.voice_xp, user.stream_xp, user.last_active_date, user.user_id))
        conn.commit()

def modify_user_xp(user_id, xp_type, amount):
    user = get_or_create_user(user_id)
    attr = f"{xp_type}_xp"
    current = getattr(user, attr, 0)
    setattr(user, attr, max(0, current + amount))
    update_user(user)
