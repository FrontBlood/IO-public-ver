# === xp_tracker.py ===

import sqlite3
from database.dao_user import get_or_create_user, update_user, get_all_users
from database.daily_limit import can_gain_xp
from config.level_roles import LEVEL_ROLE_MAP
from config.constants import EXP_PARAMS
from datetime import datetime, timedelta, timezone
from config.constants import DAILY_CAP, MIN_XP_FLOOR, INACTIVITY_DAYS_THRESHOLD, XP_DECAY_ENABLED, DB_PATH
import asyncio
semaphore = asyncio.Semaphore(3)  # 控制并发任务数
DELAY_BETWEEN_ACTIONS = 1.5       # 每次身份组变动之间的延迟

def get_required_xp(xp_type: str, level: int) -> int:
    if level <= 0:
        return 0
    base, scale = EXP_PARAMS[xp_type]
    return int(base * (scale ** (level - 1)))


def get_level_from_xp(xp_type: str, xp: int) -> int:
    level = 0
    while xp >= get_required_xp(xp_type, level + 1):
        level += 1
    return level

async def apply_xp_and_check_level(user, xp_type, amount, member=None):
    current_xp = getattr(user, f"{xp_type}_xp")
    old_level = get_level_from_xp(xp_type, current_xp)   # 修正点在这里！！
    
    new_xp = current_xp + amount
    setattr(user, f"{xp_type}_xp", new_xp)

    new_level = get_level_from_xp(xp_type, new_xp)
    leveled_up = new_level > old_level
    user.last_active_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    update_user(user)

    return leveled_up, user


async def decay_inactive_users(bot):
    if not XP_DECAY_ENABLED:
        return

    today = datetime.now(timezone.utc).date()
    users = get_all_users()

    for user in users:
        try:
            if user.last_active_date:
                last_active = datetime.strptime(user.last_active_date, "%Y-%m-%d").date()
            else:
                last_active = today
        except Exception:
            last_active = today

        inactive_days = (today - last_active).days
        inactive_days = max(0, inactive_days)

        if inactive_days >= INACTIVITY_DAYS_THRESHOLD:
            # 查找成员对象
            member = None
            for guild in bot.guilds:
                member = guild.get_member(int(user.user_id))
                if member:
                    break

            # 执行经验衰减
            updated = False
            for xp_type in ["text", "voice", "stream"]:
                daily_cap = DAILY_CAP.get(xp_type, 0)
                floor = MIN_XP_FLOOR.get(xp_type, 0)
                current_xp = getattr(user, f"{xp_type}_xp")

                if current_xp <= floor:
                    new_xp = current_xp
                else:
                    new_xp = max(floor, current_xp - daily_cap)

                if new_xp != current_xp:
                    setattr(user, f"{xp_type}_xp", new_xp)
                    updated = True

            if updated:
                update_user(user)

                # 检查是否需要调整身份组
                if member:
                    from services.role_utils import check_level_change
                    async with semaphore:
                        try:
                            await check_level_change(member, user)
                            await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
                        except Exception:
                            pass
