# services/mengmeng_service.py
from datetime import datetime, date, timedelta, timezone
import discord

from config.mengmeng_config import (
    MENGMENG_INITIAL_COINS,
    MENGMENG_CHECKIN_STREAK_TARGET, MENGMENG_CHECKIN_REWARD,
    MENGMENG_LEVEL_TARGET, MENGMENG_LEVEL_REWARD,
    MENGMENG_VOICE_TOTAL_CAP, MENGMENG_VOICE_REWARD_COINS,
    MENGMENG_THANKS_DAILY_CAP, MENGMENG_THANKS_COST,
    MENGMENG_ROLE_ID, WELCOME_ROLE_ID
)
from database.mengmeng_dao import (
    init_mengmeng_tables, ensure_user, get_flags, set_flag,
    get_balance, add_balance,
    get_thanks_used, inc_thanks_used
)

def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def init_mengmeng():
    init_mengmeng_tables()

def has_role(member: discord.Member, role_id: int) -> bool:
    role = member.guild.get_role(int(role_id))
    return bool(role and role in member.roles)

async def activate_targets(operator: discord.Member, targets: list[discord.Member]) -> str:
    guild = operator.guild
    mm_role = guild.get_role(int(MENGMENG_ROLE_ID))
    if not mm_role:
        return "❌ 找不到萌萌身份组（请检查 MENGMENG_ROLE_ID）。"

    activated = 0
    granted = 0
    for m in targets:
        if m.bot:
            continue
        ensure_user(str(m.id))
        flags = get_flags(str(m.id))
        gave_initial = int(flags[0]) if flags else 0

        # 补身份组
        if mm_role not in m.roles:
            try:
                await m.add_roles(mm_role, reason=f"萌萌激活 by {operator.id}")
            except discord.Forbidden:
                continue

        activated += 1
        if not gave_initial:
            add_balance(str(m.id), +MENGMENG_INITIAL_COINS, "萌萌激活初始币", from_user=str(operator.id), to_user=str(m.id))
            set_flag(str(m.id), "gave_initial", 1)
            granted += 1

    return f"✅ 已处理 {activated} 人；其中 {granted} 人获得初始 {MENGMENG_INITIAL_COINS} 枚萌新币。"

def grant_checkin_reward_if_eligible(user_id: str, streak: int) -> bool:
    # 必须先达到目标天数
    if streak < MENGMENG_CHECKIN_STREAK_TARGET:
        return False

    ensure_user(user_id)
    flags = get_flags(user_id) or (0, 0, 0, "", 0, "")

    # ✅ 资格限制：必须是“萌萌体系用户”（被激活过，gave_initial=1）
    # flags[0] = gave_initial
    if int(flags[0]) != 1:
        return False

    # flags[1] = gave_checkin_7d（去重）
    if int(flags[1]) == 1:
        return False

    add_balance(
        user_id,
        +MENGMENG_CHECKIN_REWARD,
        f"连续签到达{MENGMENG_CHECKIN_STREAK_TARGET}天奖励",
        to_user=user_id
    )
    set_flag(user_id, "gave_checkin_7d", 1)
    return True

def grant_level_reward_if_eligible(user_id: str, total_level: int) -> bool:
    # 必须达到目标等级
    if total_level < MENGMENG_LEVEL_TARGET:
        return False

    ensure_user(user_id)
    flags = get_flags(user_id) or (0, 0, 0, "", 0, "")

    # ✅ 资格限制：必须是“萌萌体系用户”（被激活过，gave_initial=1）
    if int(flags[0]) != 1:
        return False

    # flags[2] = gave_level_5（去重）
    if int(flags[2]) == 1:
        return False

    add_balance(
        user_id,
        +MENGMENG_LEVEL_REWARD,
        f"社区等级达{MENGMENG_LEVEL_TARGET}奖励",
        to_user=user_id
    )
    set_flag(user_id, "gave_level_5", 1)
    return True
def thanks(sender_id: str, receiver_id: str, today: date) -> tuple[bool, str]:
    if sender_id == receiver_id:
        return False, "❌ 不能感谢自己。"

    used = get_thanks_used(sender_id, today.isoformat())
    if used >= MENGMENG_THANKS_DAILY_CAP:
        return False, f"❌ 今日感谢次数已达上限（{MENGMENG_THANKS_DAILY_CAP}次）。"

    bal = get_balance(sender_id)
    if bal < MENGMENG_THANKS_COST:
        return False, "❌ 你的萌新币不足。"

    add_balance(sender_id, -MENGMENG_THANKS_COST, "感谢支出", from_user=sender_id, to_user=receiver_id)
    add_balance(receiver_id, +MENGMENG_THANKS_COST, "收到感谢", from_user=sender_id, to_user=receiver_id)
    inc_thanks_used(sender_id, today.isoformat(), 1)
    return True, "✅ 感谢已送达！"
