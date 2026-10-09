# shop_config.py

import asyncio
from database.dao_user import get_or_create_user, update_user
from services.xp_tracker import apply_xp_and_check_level
from database.shop_database import ShopDatabase
from database.currency import get_balance, subtract_balance
from services.role_utils import check_level_change

SUPPORTED_TYPES = {"xp", "checkin"}
TYPE_HANDLER_MAP = {}

def register_handler(item_type):
    def wrapper(func):
        TYPE_HANDLER_MAP[item_type] = func
        return func
    return wrapper

@register_handler("xp")
async def handle_xp_purchase(user_id, item, member=None):
    item_id, name, desc, base_price, item_type, effect_value, _ = item
    db = ShopDatabase()

    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM shop_sales WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    count = cursor.fetchone()[0]
    conn.close()

    if count >= 10:
        return False, f"📦 该商品限购10次，你已达到上限"

    if "文字" in name:
        if count < 3:
            dynamic_price = 15
        elif count < 6:
            dynamic_price = 18
        else:
            dynamic_price = 21
    elif "语音" in name:
        if count < 3:
            dynamic_price = 12
        elif count < 6:
            dynamic_price = 15
        else:
            dynamic_price = 18
    elif "直播" in name:
        if count < 3:
            dynamic_price = 10
        elif count < 6:
            dynamic_price = 12
        else:
            dynamic_price = 15
    else:
        return False, f"⚠️ 无法识别经验类型（商品名应包含“文字/语音/直播”）"

    if get_balance(user_id) < dynamic_price:
        return False, f"💸 当前第 {count+1} 次价格为 {dynamic_price} 晶核，余额不足"

    subtract_balance(user_id, dynamic_price)

    if "文字" in name:
        xp_type = "text"
    elif "语音" in name:
        xp_type = "voice"
    elif "直播" in name:
        xp_type = "stream"

    user = get_or_create_user(user_id)
    leveled_up, user = await apply_xp_and_check_level(user, xp_type, effect_value)
    update_user(user)
    if leveled_up and member:
        await check_level_change(member, user)

    return True, f"获得 {effect_value} 点{xp_type}经验（第 {count+1} 次购买，花费 {dynamic_price} 晶核）"


def _get_user_item_purchase_count(user_id, item_id):
    db = ShopDatabase()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM shop_sales WHERE user_id = ? AND item_id = ?",
        (user_id, item_id),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def calculate_checkin_price(base_price, count):
    stage = count // 10
    index = count % 10
    stage_base = base_price

    for _ in range(stage):
        stage_base = stage_base * 2 + base_price

    return stage_base + index


@register_handler("checkin")
async def handle_checkin_purchase(user_id, item, member=None):
    item_id, name, desc, base_price, item_type, effect_value, _ = item
    count = _get_user_item_purchase_count(user_id, item_id)
    price = calculate_checkin_price(base_price, count)

    from datetime import datetime, timezone
    from database.checkin_database import get_checkin_data, update_checkin_data

    row = get_checkin_data(user_id)
    if not row:
        return False, "⚠️ 你还没有签到记录，无法使用时空传送。"

    _last_checkin, streak, max_streak = row
    if streak >= max_streak:
        return False, "📌 你的连续签到已经是历史最高，无需补签。"

    if get_balance(user_id) < price:
        return False, f"💸 当前第 {count + 1} 次价格为 {price} 晶核，余额不足。"

    subtract_balance(user_id, price)
    now = datetime.now(timezone.utc).isoformat()
    update_checkin_data(user_id, now, max_streak, max_streak)

    return True, (
        f"✨ 时空传送成功！连续签到已恢复为 **{max_streak} 天**，并记录为今天已签到。\n"
        f"💸 本次价格：{price} 晶核"
    )


def get_checkin_price(user_id, item):
    item_id = item[0]
    base_price = item[3]
    count = _get_user_item_purchase_count(user_id, item_id)
    return calculate_checkin_price(base_price, count)


handle_checkin_purchase.get_price = get_checkin_price

# ✅ 注册价格逻辑（基于 user_id 和 item）
def get_price(user_id, item):
    item_id, name = item[0], item[1]
    db = ShopDatabase()
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM shop_sales WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    count = cursor.fetchone()[0]
    conn.close()

    if "文字" in name:
        return 15 if count < 3 else (18 if count < 6 else 21)
    elif "语音" in name:
        return 12 if count < 3 else (15 if count < 6 else 18)
    elif "直播" in name:
        return 10 if count < 3 else (12 if count < 6 else 15)
    else:
        return 99999

handle_xp_purchase.get_price = get_price
