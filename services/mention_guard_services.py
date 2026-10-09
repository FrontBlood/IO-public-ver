import time
import discord
from database.dao_user import get_or_create_user
from services.xp_tracker import get_level_from_xp

from config.mention_guard_config import (
    MENTION_MIN_TOTAL_LEVEL,
    EXEMPT_ROLE_IDS,
    CHANNEL_RULES,
)

# ---- 短期缓存：避免同一个人短时间内多次提及导致频繁查库 ----
# key: user_id(int) -> (expire_ts, total_level)
_LEVEL_CACHE: dict[int, tuple[float, int]] = {}
_LEVEL_CACHE_TTL = 30.0  # 秒，够用且安全

def calc_total_level(member: discord.Member) -> int:
    now = time.time()
    cached = _LEVEL_CACHE.get(member.id)
    if cached and cached[0] > now:
        return cached[1]

    # 这里假设 get_or_create_user 是同步的
    user = get_or_create_user(str(member.id))
    text_lv = get_level_from_xp("text", user.text_xp)
    voice_lv = get_level_from_xp("voice", user.voice_xp)
    stream_lv = get_level_from_xp("stream", user.stream_xp)
    total = int(text_lv + voice_lv + stream_lv)

    _LEVEL_CACHE[member.id] = (now + _LEVEL_CACHE_TTL, total)
    return total

def has_any_role(member: discord.Member, role_ids: list[int]) -> bool:
    if not role_ids:
        return False
    s = {r.id for r in member.roles}
    return any(rid in s for rid in role_ids)

def is_mentioning(message: discord.Message) -> bool:
    # 如果是回复消息 → 一律允许（不算违规提及）
    if message.reference is not None:
        return False

    # mention_everyone 同时覆盖 @everyone 和 @here
    return bool(
        message.mention_everyone
        or message.mentions
        or message.role_mentions
    )

def resolve_rule_key(message: discord.Message) -> int | None:
    ch = message.channel
    if isinstance(ch, discord.Thread):
        if ch.id in CHANNEL_RULES:
            return ch.id
        if ch.parent_id in CHANNEL_RULES:
            return ch.parent_id
        return None
    return ch.id if ch.id in CHANNEL_RULES else None

def should_delete_for_mentions(message: discord.Message) -> tuple[bool, str]:
    if message.guild is None or message.author.bot:
        return (False, "ignore")
    if not isinstance(message.author, discord.Member):
        return (False, "not_member")
    if not is_mentioning(message):
        return (False, "no_mention")

    member: discord.Member = message.author

    # 频道专管（优先）
    rk = resolve_rule_key(message)
    if rk is not None:
        rule = CHANNEL_RULES[rk]
        mode = rule.get("mode")

        if mode == "deny_all":
            return (True, "channel:deny_all")

        if mode == "min_level":
            need = int(rule.get("min_total_level", MENTION_MIN_TOTAL_LEVEL))
            try:
                total = calc_total_level(member)
            except Exception as e:
                # 失败时建议“放行”避免误杀；你想失败即拦截也可以改成 True
                return (False, f"level_calc_error:{type(e).__name__}")
            return (total < need, f"channel:min_level total={total} need={need}")

    # 例外：萌新放行
    if has_any_role(member, EXEMPT_ROLE_IDS):
        return (False, "exempt:newbee")


    # 全频：总等级 >= 门槛才允许提及
    try:
        total = calc_total_level(member)
    except Exception as e:
        return (False, f"level_calc_error:{type(e).__name__}")
    return (total < MENTION_MIN_TOTAL_LEVEL, f"global:min_level total={total} need={MENTION_MIN_TOTAL_LEVEL}")
