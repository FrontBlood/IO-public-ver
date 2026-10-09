import discord
from discord.ext import commands
from database.dao_user import get_or_create_user, update_user
from services.currency_service import convert_exp_to_currency, transfer_currency
from database.currency import add_balance, subtract_balance, get_balance
from services.role_utils import check_level_change
from config.constants import CURRENCY_NAME
from services.xp_tracker import get_level_from_xp

def setup(bot):

    # === 玩家指令：兑换经验为遗迹晶核 ===
    @bot.command(name="兑换晶核")
    async def convert_exp(ctx, xp_type: str, amount: int):  # 经验点保留整数
        user = get_or_create_user(str(ctx.author.id))

        if xp_type not in ("text", "voice", "stream"):
            return await ctx.send("❌ 类型必须是 text / voice / stream", reference=ctx.message, mention_author=True)

        current_xp = getattr(user, f"{xp_type}_xp")

        if current_xp < amount:
            return await ctx.send(f"❌ 你的{xp_type}经验不足，当前仅有 {current_xp} 点。", reference=ctx.message, mention_author=True)

        if amount < 100:
            return await ctx.send("❌ 兑换经验不足，至少需要100点经验。", reference=ctx.message, mention_author=True)

        crystal_amount = round(amount / 100, 2)
        setattr(user, f"{xp_type}_xp", current_xp - amount)
        add_balance(user.user_id, crystal_amount)
        update_user(user)
        user = get_or_create_user(str(ctx.author.id))

        await check_level_change(ctx.author, user)

        await ctx.send(
            f"✅ 成功兑换 {amount} 点 {xp_type} 经验为 {crystal_amount:.2f} {CURRENCY_NAME}！",
            reference=ctx.message,
            mention_author=True
        )

    # === 玩家指令：遗迹晶核转账 ===
    # === 玩家指令：遗迹晶核转账（仅限等级5及以上） ===
    @bot.command(name="转账晶核")
    async def transfer_crystal(ctx, member: discord.Member, amount: float):
        sender_id = str(ctx.author.id)
        receiver_id = str(member.id)

        user = get_or_create_user(sender_id)

        total_level = (
            get_level_from_xp("text", user.text_xp)
            + get_level_from_xp("voice", user.voice_xp)
            + get_level_from_xp("stream", user.stream_xp)
        )

        if total_level < 5:
            return await ctx.send("❌ 你需要达到等级 5 才能使用转账功能！", reference=ctx.message, mention_author=True)

        if sender_id == receiver_id:
            return await ctx.send("❌ 不能转账给自己！", reference=ctx.message, mention_author=True)

        try:
            amount_transferred, fee = transfer_currency(sender_id, receiver_id, amount)
            await ctx.send(
                f"✅ 成功转账 {amount_transferred:.2f} {CURRENCY_NAME} 给 {member.mention}，手续费 {fee:.2f} {CURRENCY_NAME}。",
                reference=ctx.message,
                mention_author=True
            )
        except ValueError as e:
            await ctx.send(f"❌ {str(e)}", reference=ctx.message, mention_author=True)

    # === 管理员指令：增加指定玩家晶核 ===
    @bot.command(name="增加晶核")
    @commands.has_permissions(administrator=True)
    async def admin_add_crystal(ctx, member: discord.Member, amount: float):
        add_balance(str(member.id), amount)
        await ctx.send(
            f"✅ 已增加 {amount:.2f} {CURRENCY_NAME} 给 {member.mention}。",
            reference=ctx.message,
            mention_author=True
        )

    # === 管理员指令：减少指定玩家晶核 ===
    @bot.command(name="减少晶核")
    @commands.has_permissions(administrator=True)
    async def admin_subtract_crystal(ctx, member: discord.Member, amount: float):
        try:
            subtract_balance(str(member.id), amount)
            await ctx.send(
                f"✅ 已扣除 {amount:.2f} {CURRENCY_NAME} 从 {member.mention}。",
                reference=ctx.message,
                mention_author=True
            )
        except ValueError as e:
            await ctx.send(f"❌ {str(e)}", reference=ctx.message, mention_author=True)

    # === 玩家指令：查看自己晶核余额 ===
    @bot.command(name="晶核余额")
    async def check_crystal_balance(ctx):
        balance = get_balance(str(ctx.author.id))
        await ctx.send(
            f"💎 你当前持有 {balance:.2f} {CURRENCY_NAME}。",
            reference=ctx.message,
            mention_author=True
        )
