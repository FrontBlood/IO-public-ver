from discord.ext import commands
from services.drop_service import DropService
from database.drop_log import get_total_drops
from config.constants import DROP_ADMIN_ROLE_IDS

drop_service = DropService()

def setup(bot):
    @bot.command(name="开启掉落")
    async def enable_drop(ctx):
        if not any(role.id in DROP_ADMIN_ROLE_IDS for role in ctx.author.roles):
            return await ctx.send("❌ 你没有权限执行此操作。", reference=ctx.message, mention_author=True)

        if drop_service.is_active():
            await ctx.send("⚠️ 掉落功能已在运行中。", reference=ctx.message, mention_author=True)
        else:
            drop_service.start(bot)
            await ctx.send(f"✅ 掉落系统已启动，每 {drop_service.drop_interval_minutes} 分钟发放一次晶核。", reference=ctx.message, mention_author=True)

    @bot.command(name="关闭掉落")
    async def disable_drop(ctx):
        if not any(role.id in DROP_ADMIN_ROLE_IDS for role in ctx.author.roles):
            return await ctx.send("❌ 你没有权限执行此操作。", reference=ctx.message, mention_author=True)

        if not drop_service.is_active():
            await ctx.send("⚠️ 掉落系统当前未启动。", reference=ctx.message, mention_author=True)
        else:
            drop_service.stop()
            await ctx.send("🛑 掉落系统已关闭。", reference=ctx.message, mention_author=True)

    @bot.command(name="掉落统计")
    async def drop_stats(ctx):
        if not any(role.id in DROP_ADMIN_ROLE_IDS for role in ctx.author.roles):
            return await ctx.send("❌ 你没有权限执行此操作。", reference=ctx.message, mention_author=True)

        total = get_total_drops()
        await ctx.send(f"📊 当前累计通过掉落系统发放的遗迹晶核总数为：**{total}**", reference=ctx.message, mention_author=True)

    @bot.command(name="设置掉落比例")
    async def set_drop_rate(ctx, percent: int):
        if not any(role.id in DROP_ADMIN_ROLE_IDS for role in ctx.author.roles):
            return await ctx.send("❌ 你没有权限执行此操作。", reference=ctx.message, mention_author=True)

        if not 1 <= percent <= 100:
            return await ctx.send("❌ 掉落比例应在 1~100 之间。", reference=ctx.message, mention_author=True)

        drop_service.drop_rate_percent = percent
        await ctx.send(f"✅ 掉落抽选比例已设置为 {percent}%。", reference=ctx.message, mention_author=True)

    @bot.command(name="设置掉落数量")
    async def set_drop_amount(ctx, amount: int):
        if not any(role.id in DROP_ADMIN_ROLE_IDS for role in ctx.author.roles):
            return await ctx.send("❌ 你没有权限执行此操作。", reference=ctx.message, mention_author=True)

        if amount <= 0:
            return await ctx.send("❌ 掉落数量必须大于 0。", reference=ctx.message, mention_author=True)

        drop_service.drop_amount = amount
        await ctx.send(f"✅ 每人掉落晶核数量已设置为 {amount} 枚。", reference=ctx.message, mention_author=True)

    @bot.command(name="设置掉落周期")
    async def set_drop_interval(ctx, minutes: int):
        if not any(role.id in DROP_ADMIN_ROLE_IDS for role in ctx.author.roles):
            return await ctx.send("❌ 你没有权限执行此操作。", reference=ctx.message, mention_author=True)

        if not 1 <= minutes <= 120:
            return await ctx.send("❌ 周期必须在 1 ~ 120 分钟之间。", reference=ctx.message, mention_author=True)

        drop_service.drop_interval_minutes = minutes
        if drop_service.is_active():
            drop_service._drop_loop.change_interval(minutes=minutes)

        await ctx.send(f"✅ 掉落周期已更新为每 **{minutes} 分钟** 发放一次。", reference=ctx.message, mention_author=True)
