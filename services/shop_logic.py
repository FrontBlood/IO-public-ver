# shop_logic.py

import time
from database.currency import get_balance, subtract_balance
from database.dao_user import get_or_create_user, update_user
from services.xp_tracker import apply_xp_and_check_level
from config.shop_config import TYPE_HANDLER_MAP
from database.shop_database import ShopDatabase
from services.checkin_event_service import is_checkin_shop_item_locked

class ShopLogic:
    def __init__(self):
        self.db = ShopDatabase()

    def list_items(self):
        return self.db.get_all_items()

    def list_items_for_user(self, user_id):
        items = self.db.get_all_items()
        enriched_items = []

        conn = self.db.connect()
        cursor = conn.cursor()

        for item in items:
            item_id, name, desc, _, item_type, effect_value, stock = item
            if item_type == "checkin" and is_checkin_shop_item_locked():
                continue
            cursor.execute("SELECT COUNT(*) FROM shop_sales WHERE user_id = ? AND item_id = ?", (user_id, item_id))
            count = cursor.fetchone()[0]
            handler = TYPE_HANDLER_MAP.get(item_type)
            if handler and hasattr(handler, "get_price"):
                price = handler.get_price(user_id, item)
            else:
                price = 99999
            enriched_items.append((item_id, name, desc, price, item_type, effect_value, stock))

        conn.close()
        return enriched_items

    async def buy_item(self, user_id, item_id, member=None):
        item = self.db.get_item_by_id(item_id)
        if not item:
            return False, "❌ 商品不存在。"

        _, name, desc, _, item_type, effect_value, stock = item

        if item_type == "checkin" and is_checkin_shop_item_locked():
            return False, "签到活动期间，时空传送暂时下架。"

        if item_type not in TYPE_HANDLER_MAP:
            return False, f"❌ 商品类型 `{item_type}` 不支持。"

        handler = TYPE_HANDLER_MAP[item_type]

        try:
            success, message = await handler(user_id, item, member=member)
        except Exception as e:
            return False, f"⚠️ 执行处理器失败：{str(e)}"

        if not success:
            return False, message

        if stock > 0:
            self.db.reduce_stock(item_id)

        self.db.log_sale(item_id, user_id, handler.get_price(user_id, item))
        return True, f"✅ 成功购买 {name}，{message}"

    def get_sales_statistics(self, item_id):
        now = int(time.time())
        week_ago = now - 7 * 86400
        season_ago = now - 90 * 86400
        return {
            "total": self.db.get_sales_count(item_id, 0),
            "weekly": self.db.get_sales_count(item_id, week_ago),
            "season": self.db.get_sales_count(item_id, season_ago)
        }

    def get_user_purchase_history(self, user_id, limit=10, offset=0):
        records = self.db.get_user_purchases(user_id, limit, offset)
        result = []
        for ts, name, price, item_type in records:
            time_str = time.strftime('%Y-%m-%d %H:%M', time.gmtime(ts))
            result.append(f"📦 `{time_str}` - 购买了 **{name}**（{price} 核，类型：{item_type}）")
        return result
