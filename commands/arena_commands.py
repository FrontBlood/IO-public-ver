# arena_commands.py

from discord.ext import commands
from discord import Embed
from services.arena_logic import update_arena_state, settle_battle, clear_arena, arena_state
from database.arena_dao import record_victory, get_user_stats

# 假设配置中有频道 ID
RADIANT_CHANNEL_ID = 0
DIRE_CHANNEL_ID = 0
ARENA_MANAGER_ROLE_ID = 0

def has_arena_permission(ctx):
    return any(role.id == ARENA_MANAGER_ROLE_ID for role in ctx.author.roles)

def setup(bot):
    @bot.command(name="开启擂台")
    async def start_arena(ctx):
        if not has_arena_permission(ctx):
            return await ctx.send("❌ 你没有权限开启擂台。")

        guild = ctx.guild
        radiant = guild.get_channel(RADIANT_CHANNEL_ID)
        dire = guild.get_channel(DIRE_CHANNEL_ID)

        radiant_ids = [m.id for m in radiant.members if not m.bot]
        dire_ids = [m.id for m in dire.members if not m.bot]

        update_arena_state(radiant_ids, dire_ids)

        await ctx.send(f"🎮 擂台开启！\n天辉：{len(radiant_ids)}人，夜魇：{len(dire_ids)}人")

    @bot.command(name="结算")
    async def settle(ctx):
        if not has_arena_permission(ctx):
            return await ctx.send("❌ 你没有权限进行结算。")

        winner_ids, is_defender, defended = settle_battle()

        if not winner_ids:
            return await ctx.send("⚠️ 无法判断胜者，请确认两边是否保持了足够成员重合。")

        for uid in winner_ids:
            record_victory(uid, is_defender=is_defender, defended=defended)

        total = len(winner_ids)
        side = "天辉" if winner_ids == arena_state["radiant_ids"] else "夜魇"
        result_type = "✅ 擂主胜利" if is_defender else "🔁 挑战方胜利"

        description = (
            f"🏆 胜方：{side}\n"
            f"{result_type}\n"
            + ("🛡️ 守擂成功，擂台已关闭。" if defended else "")
        )

        embed = Embed(
            title=f"擂台结算结果（{total}人）",
            description=description,
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        if defended:
            clear_arena()

    @bot.command(name="关闭擂台")
    async def force_close(ctx, side: str = None):
        if not has_arena_permission(ctx):
            return await ctx.send("❌ 你没有权限关闭擂台。")

        if side is None:
            clear_arena()
            return await ctx.send("📴 擂台已被管理员手动关闭，未记录胜负。")

        side = side.strip()
        if side not in ["天辉", "夜魇"]:
            return await ctx.send("用法错误：应为 `&关闭擂台 天辉` 或 `&关闭擂台 夜魇`，或仅输入 `&关闭擂台` 直接结束。")

        winner_ids = arena_state["radiant_ids"] if side == "天辉" else arena_state["dire_ids"]
        is_defender = arena_state["last_win_ids"] and len(set(winner_ids) & set(arena_state["last_win_ids"])) >= 4
        defended = is_defender and arena_state["streak"] >= 3

        for uid in winner_ids:
            record_victory(uid, is_defender=is_defender, defended=defended)

        clear_arena()
        description = (
            f"⚔️ 擂台已强制关闭，胜者为 {side} 方，记录擂主胜利。\n"
            + ("🛡️ 守擂成功，擂台已关闭。" if defended else "")
        )
        embed = Embed(
            title="擂台强制结算",
            description=description,
            color=0xe67e22
        )
        await ctx.send(embed=embed)

    @bot.command(name="擂台战绩")
    async def arena_stats(ctx, member: commands.MemberConverter = None):
        member = member or ctx.author
        stats = get_user_stats(str(member.id))
        if not stats:
            return await ctx.send(f"{member.mention} 暂无擂台记录。")

        def fmt_line(icon, label, value):
            return f"{icon} {label:<8} {value}"

        win_rate = (
            f"{round((stats['total_wins'] / stats['total_matches']) * 100, 1)}%"
            if stats['total_matches'] > 0 else "0%"
        )

        description = (
            f"{fmt_line('🏟️', '总场次：', stats['total_matches'])}\n"
            f"{fmt_line('🥇', '总胜场：', stats['total_wins'])}\n"
            f"{fmt_line('📈', '胜率：', win_rate)}\n"
            f"\n"
            f"{fmt_line('🛡️', '擂主胜场：', stats['defender_wins'])}\n"
            f"{fmt_line('⚔️', '挑战胜场：', stats['challenger_wins'])}\n"
            f"{fmt_line('🏰', '守擂成功：', str(stats['defends_success']) + ' 次')}\n"
        )

        embed = Embed(
            title=f"📊 {member.display_name} 的擂台战绩",
            description=description,
            color=0x3498db
        )
        await ctx.send(embed=embed)
