# shop_database.py

import sqlite3
import time
from config.constants import SHOP_DB_PATH

class ShopDatabase:
    def __init__(self, db_path=SHOP_DB_PATH):
        self.db_path = db_path
        self.init_shop_tables()
        self.insert_default_items()  # ✅ 添加初始化填充

    def connect(self):
        return sqlite3.connect(self.db_path)

    def init_shop_tables(self):
        with self.connect() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT,
                    price INTEGER,
                    type TEXT,
                    effect_value INTEGER,
                    stock INTEGER DEFAULT -1
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS shop_sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    user_id TEXT,
                    price INTEGER,
                    timestamp INTEGER
                )
            ''')
            c.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_item ON shop_sales(user_id, item_id)
            ''')
            c.execute('''
                CREATE INDEX IF NOT EXISTS idx_item_timestamp ON shop_sales(item_id, timestamp)
            ''')
            conn.commit()

    def insert_default_items(self):
        with self.connect() as conn:
            c = conn.cursor()
            default_items = [
                ("经验包-文字", "获得1000点文字经验", 15, "xp", 1000, -1),
                ("经验包-语音", "获得1000点语音经验", 12, "xp", 1000, -1),
                ("经验包-直播", "获得1000点直播经验", 10, "xp", 1000, -1),
                ("时空传送", "寻回失落的历史抵达签到的巅峰", 20, "checkin", 0, -1),
            ]

            for item in default_items:
                exists = c.execute(
                    "SELECT 1 FROM shop_items WHERE name = ? LIMIT 1",
                    (item[0],),
                ).fetchone()
                if not exists:
                    c.execute('''
                    INSERT INTO shop_items (name, description, price, type, effect_value, stock)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', item)

            conn.commit()

    def get_all_items(self):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM shop_items").fetchall()

    def get_item_by_id(self, item_id):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM shop_items WHERE item_id=?", (item_id,)).fetchone()

    def reduce_stock(self, item_id):
        with self.connect() as conn:
            conn.execute("UPDATE shop_items SET stock = stock - 1 WHERE item_id=? AND stock > 0", (item_id,))
            conn.commit()

    def log_sale(self, item_id, user_id, price):
        with self.connect() as conn:
            conn.execute('''
                INSERT INTO shop_sales (item_id, user_id, price, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (item_id, user_id, price, int(time.time())))
            conn.commit()

    def get_sales_count(self, item_id, start_ts, end_ts=None):
        with self.connect() as conn:
            if end_ts:
                result = conn.execute('''
                    SELECT SUM(price) FROM shop_sales 
                    WHERE item_id=? AND timestamp BETWEEN ? AND ?
                ''', (item_id, start_ts, end_ts)).fetchone()
            else:
                result = conn.execute('''
                    SELECT SUM(price) FROM shop_sales 
                    WHERE item_id=? AND timestamp >= ?
                ''', (item_id, start_ts)).fetchone()
            return result[0] if result and result[0] else 0

    def get_user_purchases(self, user_id, limit=10, offset=0):
        with self.connect() as conn:
            return conn.execute('''
                SELECT s.timestamp, i.name, s.price, i.type
                FROM shop_sales s
                JOIN shop_items i ON s.item_id = i.item_id
                WHERE s.user_id=?
                ORDER BY s.timestamp DESC
                LIMIT ? OFFSET ?
            ''', (user_id, limit, offset)).fetchall()
