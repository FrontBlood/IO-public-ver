# services/mengmeng_voice_runtime.py
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
import discord

from config.mengmeng_config import (
    MENGMENG_ROLE_ID, WELCOME_ROLE_ID,
    MENGMENG_VOICE_REWARD_SECONDS,
    MENGMENG_VOICE_REWARD_COINS,
    MENGMENG_VOICE_TOTAL_CAP,
    MENGMENG_RANK_BROADCAST_INTERVAL,
)
from database.mengmeng_dao import (
    ensure_user, get_flags, set_voice_day, set_voice_week, add_balance,
    add_welcome_seconds_vc, top_welcome_in_vc
)

def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

@dataclass
class _Runtime:
    today: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    mm_seconds_today: dict[int, int] = field(default_factory=dict)
    rewarded_today: set[int] = field(default_factory=set)

    # ✅ 每个语音频道独立：开始计时 / 下一次应播报的时间戳（秒）
    eligible_since_by_vc: dict[int, float] = field(default_factory=dict)
    next_due_ts_by_vc: dict[int, float] = field(default_factory=dict)
    
R = _Runtime()

def _has_role(member: discord.Member, role_id: int) -> bool:
    role = member.guild.get_role(int(role_id))
    return bool(role and role in member.roles)

async def voice_tick_async(bot, vc: discord.VoiceChannel, interval_seconds: int = 60):
    """
    每个语音频道每分钟调用一次（在 voice_stream_tasks.py 的 member循环结束后调用）。
    负责：
    - 萌萌语音累计2小时奖励（每日一次 + 周上限）
    - 同频道有萌萌时，迎新陪伴时长累计（按vc维度累计）
    - ✅ 每小时在“该语音频道文字聊天”播报一次：萌萌进度 + 频道内迎新Top5
    """
    now = datetime.now(timezone.utc)
    if now.date() != R.today:
        R.today = now.date()
        R.mm_seconds_today.clear()
        R.rewarded_today.clear()
        R.eligible_since_by_vc.clear()
        R.next_due_ts_by_vc.clear()

    members = [m for m in vc.members if not m.bot]
    if not members:
        return

    mm_members = [m for m in members if _has_role(m, MENGMENG_ROLE_ID)]
    if not mm_members:
        return

    # 1) 萌萌语音累计 -> 满2小时给币（每天最多1次；每周最多7次）
    for m in mm_members:
        R.mm_seconds_today[m.id] = R.mm_seconds_today.get(m.id, 0) + int(interval_seconds)

        if R.mm_seconds_today[m.id] >= int(MENGMENG_VOICE_REWARD_SECONDS) and m.id not in R.rewarded_today:
            user_id = str(m.id)
            ensure_user(user_id)

            # ✅ 防 flags=None
            flags = get_flags(user_id) or (0, 0, 0, "", 0, "")
            voice_week_start = (flags[3] or "")
            voice_week_count = int(flags[4] or 0)
            voice_day = (flags[5] or "")

            today_s = R.today.isoformat()

            # ✅ 新规则：每天最多1枚，累计总上限7枚（不按周重置）
            if voice_day != today_s and voice_week_count < int(MENGMENG_VOICE_TOTAL_CAP):
                add_balance(user_id, +int(MENGMENG_VOICE_REWARD_COINS), "语音达2小时奖励", to_user=user_id)
                set_voice_day(user_id, today_s)
                # voice_week_count 字段改为“累计总次数”
                set_voice_week(user_id, voice_week_start, voice_week_count + 1)
                
            R.rewarded_today.add(m.id)

    # 2) ✅ 迎新陪伴累计：按vc维度累计
    mentors = [m for m in members if _has_role(m, WELCOME_ROLE_ID)]
    vc_id_s = str(vc.id)
    for mentor in mentors:
        add_welcome_seconds_vc(vc_id_s, str(mentor.id), int(interval_seconds))


    # 3) ✅ 满一小时才播报（按vc独立计时）
    vc_id = int(vc.id)
    now_ts = now.timestamp()
    interval = int(MENGMENG_RANK_BROADCAST_INTERVAL)

    # 若频道无人或没有萌萌 → 清计时
    if not members or not mm_members:
        R.eligible_since_by_vc.pop(vc_id, None)
        R.next_due_ts_by_vc.pop(vc_id, None)
        return

    # 第一次满足条件 → 开始计时，不播报
    if vc_id not in R.next_due_ts_by_vc:
        R.eligible_since_by_vc[vc_id] = now_ts
        R.next_due_ts_by_vc[vc_id] = now_ts + interval
        return

    # 已开始计时 → 检查是否到播报时间
    due = R.next_due_ts_by_vc[vc_id]
    
    if now_ts >= due:
        await _broadcast_status_to_voice_chat(bot, vc, mm_members, mentors)
    
        # 下一次播报时间（严格每小时）
        R.next_due_ts_by_vc[vc_id] = due + interval
async def _broadcast_status_to_voice_chat(bot, vc: discord.VoiceChannel, mm_members: list[discord.Member], mentors: list[discord.Member]):
    """
    发到“语音频道文字聊天”：
    - 萌萌：今日语音累计 & 距离2小时差多少 & 今日是否已发 & 本周次数
    - ✅ 迎新：频道内Top5（按当前vc累计）
    """
    today_s = R.today.isoformat()

    # --- 萌萌进度 ---
    mm_lines = []
    for m in mm_members:
        uid = str(m.id)
        sec = int(R.mm_seconds_today.get(m.id, 0))
        remaining = max(0, int(MENGMENG_VOICE_REWARD_SECONDS) - sec)

        flags = get_flags(uid) or (0, 0, 0, "", 0, "")
        week_count = int(flags[4] or 0)
        voice_day = (flags[5] or "")
        got_today = "✅" if (m.id in R.rewarded_today or voice_day == today_s) else "❌"

        h = sec // 3600
        mi = (sec % 3600) // 60
        rh = remaining // 3600
        rmi = (remaining % 3600) // 60

        mm_lines.append(
            f"{m.mention}  今日：{h}h {mi}m  |  距2h：{rh}h {rmi}m  |  今日发奖：{got_today}  |  总共：{week_count}/{int(MENGMENG_VOICE_TOTAL_CAP)}"
        )

    # --- ✅ 迎新Top5：频道内（按vc维度累计） ---
    top = top_welcome_in_vc(str(vc.id), 5)
    top_lines = []
    for i, (uid, sec) in enumerate(top, start=1):
        h = sec // 3600
        mi = (sec % 3600) // 60
        top_lines.append(f"{i}. <@{uid}> — {h}h {mi}m")

    embed = discord.Embed(
        title="🧾 萌萌语音奖励进度播报（每小时）",
        description=f"语音频道：**{getattr(vc, 'name', 'Unknown')}**",
        color=0x00ff99
    )
    embed.add_field(
        name="萌萌进度（确认2小时奖励）",
        value="\n".join(mm_lines) if mm_lines else "（本频道当前没有萌萌）",
        inline=False
    )
    embed.add_field(
        name="迎新陪伴 Top5（仅本频道累计）",
        value="\n".join(top_lines) if top_lines else "（暂无数据）",
        inline=False
    )

    # ✅ 发到语音频道“文字聊天”
    # 使用 partial_messageable 最稳（discord.py 2.x）
    try:
        pm = bot.get_partial_messageable(int(vc.id))
        await pm.send(embed=embed)
    except Exception:
        # 兜底：某些实现也支持 vc.send
        try:
            await vc.send(embed=embed)  # type: ignore
        except Exception:
            return
