from datetime import datetime, timezone, timedelta
from discord.ext import commands
import discord
from config.constants import TEMP_NB_ROLE_ID, EXPIRE_AFTER_DAYS, TEMP_PATH, NEWBEEMANAGER_ROLE_ID
from services.role_utils import has_role_by_id
from database.temp_roles import add_temp_role

# 用于记录每个服务器上次执行 newbee 的时间（若不使用数据库可保留）
last_newbee_check = {}

def setup(bot):
    # === 管理员指令：查看 n 天内新成员 ===
    @bot.command(name="newbee")
    @has_role_by_id(NEWBEEMANAGER_ROLE_ID)
    async def newbee(ctx, days: int):
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)
        members = ctx.guild.members
        recent_members = []

        for member in members:
            if member.bot:
                continue
            if member.joined_at and member.joined_at > cutoff:
                recent_members.append(f"<@{member.id}>")

        if recent_members:
            output = " ".join(recent_members)
            embed = discord.Embed(
                title=f"🆕 最近 {days} 天加入的新成员",
                description=f"共 {len(recent_members)} 人：\n```{output}```",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ 最近 {days} 天内没有新成员。")

        last_newbee_check[ctx.guild.id] = now

    # === 管理员指令：查看上次使用 newbee 的时间 ===
    @bot.command(name="nbcheck")
    @has_role_by_id(NEWBEEMANAGER_ROLE_ID)
    async def nbcheck(ctx):
        now = datetime.now(timezone.utc)
        last_time = last_newbee_check.get(ctx.guild.id)

        if last_time:
            delta = (now - last_time).days
            await ctx.send(f"📅 上一次使用 &newbee 指令是在 {delta} 天前。")
        else:
            await ctx.send("📭 尚未使用过 &newbee 指令。")

    # === 管理员指令：批量赋予萌新 tag ===
    @bot.command(name="nbtag")
    @has_role_by_id(NEWBEEMANAGER_ROLE_ID)
    async def nbtag(ctx, *members: discord.Member):
        if not members:
            await ctx.send("❌ 请 @ 至少一位成员。")
            return

        role = ctx.guild.get_role(TEMP_NB_ROLE_ID)
        if role is None:
            await ctx.send("❌ 角色不存在，请检查 TEMP_NB_ROLE_ID 是否正确。")
            return

        expire_time = datetime.now(timezone.utc) + timedelta(days=EXPIRE_AFTER_DAYS)
        assigned = []

        for member in members:
            try:
                await member.add_roles(role)
                add_temp_role(ctx.guild.id, member.id, role.id, expire_time)
                assigned.append(member.mention)
            except Exception:
                continue

        if assigned:
            await ctx.send(
                f"✅ 已赋予身份组 {role.mention} 给以下成员，有效期 {EXPIRE_AFTER_DAYS} 天：\n" + " ".join(assigned)
            )
