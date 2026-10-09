import discord
from discord.ext import commands

from config.constants import (
    CHECKIN_EVENT_ADMIN_USER_ID,
    CHECKIN_EVENT_REDEEM_CHANNEL_ID,
    CHECKIN_EVENT_REWARD_ROLE_ID,
    SHOPADMIN_ROLE_ID,
)
from database import checkin_event_database as event_db
from services.checkin_event_service import CheckinEventService, checkin_event_loop, parse_dt, parse_event_end_date


service = CheckinEventService()


def can_manage_checkin_event(member: discord.Member) -> bool:
    return member.id == CHECKIN_EVENT_ADMIN_USER_ID or any(role.id == SHOPADMIN_ROLE_ID for role in member.roles)


class CheckinEventSettleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="结算完成",
        style=discord.ButtonStyle.success,
        custom_id="checkin_event:settle",
    )
    async def settle(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, message = service.settle_by_admin_message(str(interaction.message.id), str(interaction.user.id))
        if ok:
            await interaction.message.edit(content=message, embed=None, view=None)
            await interaction.response.send_message("已标记结算完成。", ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


def build_status_embed() -> discord.Embed:
    event = service.current_event()
    if not event:
        return discord.Embed(title="签到活动状态", description="当前没有等待开始或进行中的签到活动。", color=0x999999)

    rewards = event_db.list_rewards(int(event["id"]))
    sent_count = sum(1 for row in rewards if row["code_sent_at"])
    redeemed_count = sum(1 for row in rewards if row["redeemed_at"])
    settled_count = sum(1 for row in rewards if row["settled_at"])
    embed = discord.Embed(
        title="签到活动状态",
        description=(
            f"状态：`{event['status']}`\n"
            f"模式：`{event['mode']}`\n"
            f"开始：{parse_dt(event['start_at']).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"结束：{parse_dt(event['end_at']).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"剩余名额：**{service.remaining_slots(event)}** / {event['reward_limit']}\n"
            f"已获名额：{len(rewards)}\n"
            f"已发码：{sent_count}\n"
            f"已兑奖：{redeemed_count}\n"
            f"已结算：{settled_count}"
        ),
        color=0x00CC99,
    )
    return embed


def build_winner_list_embed() -> discord.Embed:
    event = service.current_event()
    if not event:
        return discord.Embed(title="签到获奖名单", description="当前没有等待开始或进行中的签到活动。", color=0x999999)

    rewards = event_db.list_rewards(int(event["id"]))
    if not rewards:
        return discord.Embed(title="签到获奖名单", description="当前还没有获奖记录。", color=0x999999)

    lines = []
    for index, row in enumerate(rewards, start=1):
        sent = "已发码" if row["code_sent_at"] else "未发码"
        redeemed = "已兑奖" if row["redeemed_at"] else "未兑奖"
        settled = "已结算" if row["settled_at"] else "未结算"
        line = f"{index}. <@{row['user_id']}> (`{row['user_id']}`)｜{sent}｜{redeemed}｜{settled}"
        if row["code_send_error"]:
            line += f"｜发码失败：{row['code_send_error'][:80]}"
        lines.append(line)

    description = "\n".join(lines)
    if len(description) > 3900:
        description = description[:3900] + "\n..."
    return discord.Embed(title="签到获奖名单", description=description, color=0x00CC99)


def setup(bot: commands.Bot):
    @bot.command(name="开启签到活动")
    async def start_checkin_event(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member) or not can_manage_checkin_event(ctx.author):
            await ctx.send("你没有权限开启签到活动。")
            return
        ok, message = await service.create_event(ctx.bot, str(ctx.author.id))
        await ctx.send(message)

    @bot.command(name="测试签到活动")
    async def start_test_checkin_event(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member) or not can_manage_checkin_event(ctx.author):
            await ctx.send("你没有权限开启测试签到活动。")
            return
        ok, message = await service.create_test_event(ctx.bot, str(ctx.author.id))
        await ctx.send(message)

    @bot.command(name="关闭测试签到活动")
    async def close_test_checkin_event(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member) or not can_manage_checkin_event(ctx.author):
            await ctx.send("你没有权限关闭测试签到活动。")
            return
        ok, message = await service.close_test_event(ctx.bot, str(ctx.author.id))
        await ctx.send(message)

    @bot.command(name="签到活动状态")
    async def checkin_event_status(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member) or not can_manage_checkin_event(ctx.author):
            await ctx.send("你没有权限查看签到活动状态。")
            return
        await service.refresh_status(ctx.bot)
        event = service.current_event()
        if event and event["status"] == "scheduled":
            await service.sync_existing_eligible_rewards(ctx.bot, event, allow_scheduled=True)
        await ctx.send(embed=build_status_embed())

    @bot.command(name="签到获奖名单")
    async def checkin_event_winner_list(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member) or not can_manage_checkin_event(ctx.author):
            await ctx.send("你没有权限查看签到获奖名单。")
            return
        await ctx.send(embed=build_winner_list_embed())

    @bot.command(name="延期签到活动")
    async def extend_checkin_event(ctx: commands.Context, end_date: str):
        if not isinstance(ctx.author, discord.Member) or not can_manage_checkin_event(ctx.author):
            await ctx.send("你没有权限延期签到活动。")
            return
        try:
            end_at = parse_event_end_date(end_date)
        except ValueError:
            await ctx.send("用法：`&延期签到活动 2026-06-20`，日期按当天 01:00 UTC 结束。")
            return
        ok, message = await service.extend_latest_normal_event(ctx.bot, end_at)
        await ctx.send(message)

    @bot.command(name="签到活动权限检查")
    async def checkin_event_permission_check(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member) or not can_manage_checkin_event(ctx.author):
            await ctx.send("你没有权限检查签到活动权限。")
            return
        guild = ctx.guild
        role = guild.get_role(CHECKIN_EVENT_REWARD_ROLE_ID)
        bot_member = guild.me
        if not role:
            await ctx.send(f"未找到活动身份组：`{CHECKIN_EVENT_REWARD_ROLE_ID}`")
            return
        can_manage_role = bool(bot_member.guild_permissions.manage_roles and bot_member.top_role > role)
        embed = discord.Embed(title="签到活动权限检查", color=0x00CC99 if can_manage_role else 0xCC3333)
        embed.add_field(name="活动身份组", value=f"{role.mention} (`{role.id}`)", inline=False)
        embed.add_field(name="机器人最高身份组", value=f"{bot_member.top_role.mention} (`{bot_member.top_role.id}`)", inline=False)
        embed.add_field(name="拥有管理身份组权限", value="是" if bot_member.guild_permissions.manage_roles else "否", inline=True)
        embed.add_field(name="机器人身份组高于活动身份组", value="是" if bot_member.top_role > role else "否", inline=True)
        embed.add_field(name="可自动赋予", value="是" if can_manage_role else "否", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="兑奖")
    async def redeem_checkin_event(ctx: commands.Context, code: str):
        await service.refresh_status(ctx.bot)
        event = service.current_event()
        if not event:
            return
        if ctx.channel.id != CHECKIN_EVENT_REDEEM_CHANNEL_ID:
            return
        reward, error = service.verify_redeem(str(ctx.author.id), code.strip().upper())
        if error:
            return
        if reward["redeemed_at"] and not reward["settled_at"]:
            return
        service.mark_redeemed(reward, str(ctx.channel.id), str(ctx.message.id))
        try:
            await service.notify_admin_redeem_detail(ctx.bot, reward)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            return
        review_message = await ctx.reply(
            content="兑奖请求已发送，等待结算。",
            view=CheckinEventSettleView(),
            mention_author=True,
        )
        service.record_settlement_message(int(reward["id"]), str(review_message.id))

    @bot.listen("on_ready")
    async def _start_checkin_event_loop():
        if not getattr(bot, "_checkin_event_settle_view_registered", False):
            bot.add_view(CheckinEventSettleView())
            bot._checkin_event_settle_view_registered = True
        existing_task = getattr(bot, "_checkin_event_loop_task", None)
        if existing_task and not existing_task.done():
            return
        bot._checkin_event_loop_task = bot.loop.create_task(checkin_event_loop(bot, service))
