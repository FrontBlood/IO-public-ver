from config.achievement_definitions import ACHIEVEMENT_LIST
from database.achievement_dao import is_unlocked, unlock_achievement
from services.xp_tracker import get_or_create_user, apply_xp_and_check_level
from services.currency_service import add_balance
from database.dao_user import update_user
from database.checkin_database import get_max_streak

async def check_and_unlock_achievements(user_id, member=None):
    """
    检查用户是否满足某些成就条件，如满足则标记解锁并发放奖励。
    """
    user = get_or_create_user(user_id)
    unlocked = []

    context_data = {
        "checkin_days": get_max_streak(user_id)
    }

    for ach in ACHIEVEMENT_LIST:
        if ach.requires and not is_unlocked(user_id, ach.requires):
            continue

        if not is_unlocked(user_id, ach.id) and ach.is_unlocked(user, context_data):
            unlock_achievement(user_id, ach.id)
            user = await grant_achievement_rewards(user_id, ach, user)
            unlocked.append(ach)

    if unlocked:
        update_user(user)
        if member:
            from services.role_utils import check_level_change
            await check_level_change(member, user)

    return unlocked

async def grant_achievement_rewards(user_id, achievement, user=None):
    """
    发放成就奖励（经验与晶核）
    """
    if not user:
        user = get_or_create_user(user_id)

    reward = achievement.rewards
    if "xp" in reward:
        for xp_type, amount in reward["xp"].items():
            _, user = await apply_xp_and_check_level(user, xp_type, amount)

    if "core" in reward:
        add_balance(user_id, reward["core"])

    return user

def build_achievement_summary(user_id, user, unlocked_ids):
    """
    构建成就展示信息结构（供指令或页面调用）
    """
    from database.checkin_database import get_streak

    context_data = {
        "checkin_days": get_streak(user_id)
    }

    display = []
    unlocked_set = set(unlocked_ids)

    for ach in ACHIEVEMENT_LIST:
        if ach.requires and ach.requires not in unlocked_set:
            continue

        is_done = ach.id in unlocked_set
        summary = {
            "id": ach.id,
            "name": ach.name,
            "description": ach.description,
            "unlocked": is_done,
            "progress": ach.get_progress(user, context_data),
            "rewards": ach.rewards
        }
        display.append(summary)

    return display
