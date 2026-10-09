import discord
from discord.ext import commands

from services.avalon_service import AvalonService
from services.avalon_test_mode import send_avalon_test_panel
from services.avalon_stats import send_leaderboard, send_player_stats


def setup(bot: commands.Bot):
    service = AvalonService(bot)
    bot.avalon_service = service

    @bot.command(name="阿瓦隆", aliases=["avalon"])
    @commands.guild_only()
    async def create_avalon(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member):
            return
        ok, message = await service.create_lobby(ctx.guild, ctx.channel, ctx.author)
        if not ok:
            await ctx.send(message)

    @bot.command(name="阿瓦隆测试", aliases=["avalontest"])
    @commands.guild_only()
    async def avalon_test(ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member):
            return
        await send_avalon_test_panel(ctx, service)

    @bot.command(name="阿瓦隆战绩", aliases=["avalonstats"])
    @commands.guild_only()
    async def avalon_stats(ctx: commands.Context, member: discord.Member | None = None):
        await send_player_stats(ctx, member or ctx.author)

    @bot.command(name="阿瓦隆排行", aliases=["avalonrank", "avalonleaderboard"])
    @commands.guild_only()
    async def avalon_rank(ctx: commands.Context):
        await send_leaderboard(ctx)

    @bot.command(name="阿瓦隆规则", aliases=["avalonrules"])
    async def avalon_rules(ctx: commands.Context):
        embed = discord.Embed(title="阿瓦隆规则速查", color=0x5865F2)
        embed.description = (
            "好人需要完成三个任务；坏人需要破坏三个任务。\n"
            "每次由队长提名固定人数，全员暗投；赞成票严格过半才通过。\n"
            "队伍通过后，任务成员暗投成功/失败；好人只能成功，坏人可以任选。\n"
            "7 人及以上只有第 4 个任务需要至少两张失败牌。\n"
            "同一任务连续五次组队被否决，坏人立即获胜。\n"
            "好人完成三个任务后，刺客若命中梅林，坏人翻盘。"
        )
        embed.set_footer(text="使用 &阿瓦隆 创建游戏")
        await ctx.send(embed=embed)

    @bot.listen("on_ready")
    async def _restore_avalon_views():
        if not getattr(bot, "_avalon_views_restored", False):
            restored = await service.restore_views()
            bot._avalon_views_restored = True
            print(f"[Avalon] restored {restored} active game view(s)")

        cleanup_task = getattr(bot, "_avalon_cleanup_task", None)
        if not cleanup_task or cleanup_task.done():
            bot._avalon_cleanup_task = bot.loop.create_task(service.inactivity_cleanup_loop())
