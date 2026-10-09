# === checkin.py ===
from discord.ext import commands
import discord
from discord import Embed
from services.checkin_system import CheckinSystem
from services.checkin_event_service import CheckinEventService, is_checkin_event_locked
from services.role_utils import check_level_change
from database.dao_user import get_or_create_user
from datetime import datetime, timedelta, timezone
from config.constants import CHECKIN_EVENT_SIGNIN_CHANNEL_ID

checkin = CheckinSystem()
checkin_event = CheckinEventService()

async def get_member_display_name(ctx, user_id: str) -> str:
    member = ctx.guild.get_member(int(user_id))
    if member:
        return member.display_name
    try:
        member = await ctx.guild.fetch_member(int(user_id))
        return member.display_name
    except discord.NotFound:
        return f"用户 {user_id}"
    except discord.HTTPException:
        return f"用户 {user_id}"


def setup(bot):
    async def run_sign_in(ctx, *, check_activity: bool):
        user_id = str(ctx.author.id)
        success, streak = await checkin.sign_in(user_id)
        max_streak = checkin.get_max_streak(user_id)

        if success:
            embed = Embed(
                title="<a:BlueCheck:0> 签到成功",
                description=(
                    f"{ctx.author.mention} 你已成功签到！\n"
                    f"<:events:0> 当前连续签到：**{streak} 天**\n"
                    f"<:PlayStation_Gold_Trophy:0> 历史最高纪录：**{max_streak} 天**\n"
                    f"<:59794giveaways:0> 奖励内容：\n+50 文字经验\n+100 语音经验\n+200 直播经验\n"
                ),
                color=0x00cc99
            )

            try:
                user = get_or_create_user(user_id)
                await check_level_change(ctx.author, user)
            except Exception as e:
                print(f"⚠️ 签到后更新身份组失败：{e}")

            if check_activity:
                await checkin_event.handle_successful_checkin(ctx.bot, user_id, streak)
        else:
            now = datetime.now(timezone.utc)
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            remaining = tomorrow - now
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes = remainder // 60

            embed = Embed(
                title="⚠ 已签到",
                description=(
                    f"{ctx.author.mention} 今天已经签到过啦，明天记得来哦~\n"
                    f"⏳ 距离下次可签到还有：**{hours} 小时 {minutes} 分钟**"
                ),
                color=0xffcc00
            )

        await ctx.send(embed=embed)

    @bot.command(name="签到")
    async def sign_in_command(ctx):
        if is_checkin_event_locked():
            return
        await run_sign_in(ctx, check_activity=False)

    @bot.command(name="原神牛逼")
    async def event_sign_in_command(ctx):
        if not is_checkin_event_locked():
            await ctx.send("当前没有签到活动，请使用 `&签到`。")
            return
        if ctx.channel.id != CHECKIN_EVENT_SIGNIN_CHANNEL_ID:
            return
        await checkin_event.grant_current_event_role(ctx.bot, str(ctx.author.id))
        await run_sign_in(ctx, check_activity=True)

    @bot.command(name="签到天数")
    async def streak_command(ctx):
        user_id = str(ctx.author.id)
        streak = checkin.get_streak(user_id)
        max_streak = checkin.get_max_streak(user_id)
        await ctx.send(f"<:events:0> 当前连续签到：{streak} 天\n<:PlayStation_Gold_Trophy:0> 最高纪录：{max_streak} 天")

    @bot.command(name="签到排行")
    async def checkin_leaderboard(ctx):
        user_id = str(ctx.author.id)
        leaderboard = checkin.get_leaderboard(limit=20)
        user_rank = checkin.get_user_rank(user_id)
        user_streak = checkin.get_streak(user_id)

        if not leaderboard:
            await ctx.send("暂无签到数据。")
            return

        description = ""
        for i, (uid, streak) in enumerate(leaderboard, start=1):
            name = await get_member_display_name(ctx, uid)
            description += f"{i}. **{name}** - {streak} 天\n"

        if user_id not in [str(uid) for uid, _ in leaderboard]:
            description += f"\n🎯 你当前排名：第 **{user_rank} 名**，连续签到 **{user_streak} 天**"

        embed = Embed(
            title="<:__2:0> 当前连续签到排行榜（Top 20）",
            description=description,
            color=0x6633cc
        )

        await ctx.send(embed=embed)

    @bot.command(name="签到纪录榜")
    async def checkin_max_leaderboard(ctx):
        leaderboard = checkin.get_max_streak_leaderboard(limit=30)

        if not leaderboard:
            await ctx.send("暂无签到记录数据。")
            return

        description = ""
        for i, (uid, max_streak) in enumerate(leaderboard, start=1):
            name = await get_member_display_name(ctx, uid)
            description += f"{i}. **{name}** - {max_streak} 天\n"

        embed = Embed(
            title="<:PlayStation_Gold_Trophy:0> 历史最高签到纪录榜（Top 30）",
            description=description,
            color=0xcc3366
        )

        await ctx.send(embed=embed)
