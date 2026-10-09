# commands/mengmeng_commands.py
from __future__ import annotations

from datetime import datetime, timezone
import discord
from discord.ext import commands

from config.mengmeng_config import (
    MENGMENG_ROLE_ID,
    WELCOME_ROLE_ID,
    WELCOME_ADMIN_ROLE_ID,
    MENGMENG_THANKS_DAILY_CAP,
)
from database.mengmeng_dao import (
    get_balance,
    get_flags,
    get_thanks_used,
    sum_welcome_seconds_all,
    get_welcome_seconds_vc,
    get_welcome_rank_vc,
    sum_welcome_seconds_for_user,
)
from services.mengmeng_service import (
    init_mengmeng, activate_targets, thanks
)


def _is_admin(ctx: commands.Context) -> bool:
    # 管理员/管理服务器
    if ctx.author.guild_permissions.administrator or ctx.author.guild_permissions.manage_guild:
        return True
    # 额外管理员身份组
    if WELCOME_ADMIN_ROLE_ID and int(WELCOME_ADMIN_ROLE_ID) != 0:
        role = ctx.guild.get_role(int(WELCOME_ADMIN_ROLE_ID))
        return bool(role and role in ctx.author.roles)
    return False


def _has_role(member: discord.Member, role_id: int) -> bool:
    role = member.guild.get_role(int(role_id))
    return bool(role and role in member.roles)


def _fmt_hm(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}小时 {m}分钟"


class MengmengCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_mengmeng()

    @commands.command(name="萌萌")
    async def cmd_mengmeng(self, ctx: commands.Context, *members: discord.Member):
        """管理员激活：赋予萌萌身份组 + 初始币（支持多个成员）"""
        if not _is_admin(ctx):
            return await ctx.send("❌ 你没有权限使用该指令。")

        # ✅ 使用 discord.Member 参数转换器，避免 ctx.message.mentions 为空的问题
        targets = [m for m in members if m and (not m.bot)]
        if not targets:
            return await ctx.send("用法：`&萌萌 @用户 @用户 ...`（请至少 @ 一位成员）")

        msg = await activate_targets(ctx.author, targets)
        await ctx.send(msg)

    @commands.command(name="谢谢")
    async def cmd_thanks(self, ctx: commands.Context, member: discord.Member | None = None):
        """萌萌感谢迎新：每日最多4次"""
        if not _has_role(ctx.author, MENGMENG_ROLE_ID):
            return await ctx.send("❌ 仅萌萌身份组可使用该指令。")

        if member is None:
            return await ctx.send("用法：`&谢谢 @迎新成员`")

        if member.bot:
            return await ctx.send("❌ 不能感谢机器人。")

        if not _has_role(member, WELCOME_ROLE_ID):
            return await ctx.send("❌ 只能感谢「迎新身份组」成员。")

        today = datetime.now(timezone.utc).date()
        ok, msg = thanks(str(ctx.author.id), str(member.id), today)
        await ctx.send(msg)

    # =========================
    # ✅ 萌萌可用查询指令（管理也可用）
    # =========================
    @commands.command(name="萌萌查询")
    async def cmd_mengmeng_query(self, ctx: commands.Context, member: discord.Member | None = None):
        """
        萌萌可用：查询自己的萌新币/奖励状态/今日感谢剩余
        管理也可用：可通过 @目标 查询他人
        """
        if not (_has_role(ctx.author, MENGMENG_ROLE_ID) or _is_admin(ctx)):
            return await ctx.send("❌ 仅萌萌身份组或管理可使用该指令。")

        # 默认查自己；管理可查他人
        target = ctx.author
        if member is not None:
            if not _is_admin(ctx):
                return await ctx.send("❌ 你只能查询自己（管理员才可查他人）。")
            target = member

        uid = str(target.id)
        bal = get_balance(uid)
        flags = get_flags(uid) or (0, 0, 0, "", 0, "")
        gave_initial = int(flags[0])
        gave_checkin7 = int(flags[1])
        gave_level5 = int(flags[2])
        voice_total = int(flags[4] or 0)
        voice_day = (flags[5] or "")

        today_s = datetime.now(timezone.utc).date().isoformat()
        got_voice_today = "✅" if voice_day == today_s else "❌"

        # 今日感谢剩余：按“执行者”计算（只有萌萌身份组才有意义）
        used = get_thanks_used(str(ctx.author.id), today_s)
        remain = max(0, int(MENGMENG_THANKS_DAILY_CAP) - int(used))

        embed = discord.Embed(
            title="🧾 萌萌查询",
            description=f"对象：{target.mention}",
            color=0x00ff99
        )
        embed.add_field(name="萌新币余额", value=str(bal), inline=True)
        embed.add_field(name="今日感谢剩余", value=f"{remain}/{MENGMENG_THANKS_DAILY_CAP}", inline=True)
        embed.add_field(
            name="奖励状态",
            value=(
                f"激活初始币：{'✅' if gave_initial else '❌'}\n"
                f"签到7天奖励：{'✅' if gave_checkin7 else '❌'}\n"
                f"等级5奖励：{'✅' if gave_level5 else '❌'}"
            ),
            inline=False
        )
        embed.add_field(
            name="语音2小时奖励",
            value=f"累计已得：{voice_total}/7\n今日是否已发：{got_voice_today}",
            inline=False
        )
        await ctx.send(embed=embed)

    # =========================
    # ✅ 迎新可用查询指令（管理也可用）
    # =========================
    @commands.command(name="迎新查询")
    async def cmd_welcome_query(self, ctx: commands.Context, member: discord.Member | None = None):
        """
        迎新可用：查询自己的萌新币、总陪伴时长、当前语音频道内陪伴排行
        管理也可用：可通过 @目标 查询他人（目标必须是迎新身份组）
        """
        if not (_has_role(ctx.author, WELCOME_ROLE_ID) or _is_admin(ctx)):
            return await ctx.send("❌ 仅迎新身份组或管理可使用该指令。")

        target = ctx.author
        if member is not None:
            if not _is_admin(ctx):
                return await ctx.send("❌ 你只能查询自己（管理员才可查他人）。")
            target = member

        if not _has_role(target, WELCOME_ROLE_ID):
            return await ctx.send("❌ 目标不是迎新身份组成员。")

        uid = str(target.id)
        bal = get_balance(uid)
        total_sec_all = sum_welcome_seconds_for_user(uid)

        # 当前所在语音频道（用于“频道内累计/排名”）
        vc = None
        if isinstance(target, discord.Member) and target.voice and target.voice.channel:
            if isinstance(target.voice.channel, discord.VoiceChannel):
                vc = target.voice.channel

        embed = discord.Embed(
            title="🧾 迎新查询",
            description=f"对象：{target.mention}",
            color=0x00ff99
        )
        embed.add_field(name="萌新币余额", value=str(bal), inline=True)
        embed.add_field(name="总陪伴时长（全频道累计）", value=_fmt_hm(total_sec_all), inline=True)

        if vc:
            vc_id = str(vc.id)
            sec_vc = get_welcome_seconds_vc(vc_id, uid)
            rank_vc = get_welcome_rank_vc(vc_id, uid)
            embed.add_field(
                name="当前语音频道陪伴",
                value=(
                    f"频道：**{vc.name}**\n"
                    f"本频道累计：{_fmt_hm(sec_vc)}\n"
                    f"本频道排名：#{rank_vc if rank_vc else '—'}"
                ),
                inline=False
            )
        else:
            embed.add_field(
                name="当前语音频道陪伴",
                value="你当前不在语音频道内（加入语音后可显示“本频道累计/排名”）。",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="迎新管理")
    async def cmd_admin(self, ctx: commands.Context):
        """管理面板：萌萌/迎新余额 + 迎新总陪伴时长"""
        if not _is_admin(ctx):
            return await ctx.send("❌ 你没有权限使用该指令。")

        mm_role = ctx.guild.get_role(int(MENGMENG_ROLE_ID))
        welcome_role = ctx.guild.get_role(int(WELCOME_ROLE_ID))
        if not mm_role or not welcome_role:
            return await ctx.send("❌ 未配置 萌萌/迎新 身份组ID。")

        mm_members = [m for m in ctx.guild.members if (not m.bot and mm_role in m.roles)]
        mentors = [m for m in ctx.guild.members if (not m.bot and welcome_role in m.roles)]

        def _fmt_bal(members, limit=15):
            pairs = [(m, get_balance(str(m.id))) for m in members]
            pairs.sort(key=lambda x: x[1], reverse=True)
            lines = [f"{m.mention}：{bal}" for m, bal in pairs[:limit]]
            if len(pairs) > limit:
                lines.append(f"...（共{len(pairs)}人）")
            return "\n".join(lines) if lines else "（无）"

        total_sec = sum_welcome_seconds_all()

        embed = discord.Embed(
            title="📊 迎新系统统计",
            color=0x00ff99
        )
        embed.add_field(name="萌萌成员余额", value=_fmt_bal(mm_members), inline=False)
        embed.add_field(name="迎新成员余额", value=_fmt_bal(mentors), inline=False)
        embed.add_field(name="迎新总陪伴时长（全频道累计）", value=_fmt_hm(total_sec), inline=False)

        await ctx.send(embed=embed)


async def add_cog_on_ready(bot: commands.Bot):
    await bot.add_cog(MengmengCommands(bot))
