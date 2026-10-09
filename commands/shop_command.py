# 重构后的 shop_command.py

import discord
from discord.ext import commands
from discord.ui import View, Button
from services.shop_logic import ShopLogic
from database.shop_database import ShopDatabase
from config.constants import SHOPADMIN_ROLE_ID

shop = ShopLogic()
db = ShopDatabase()

# ✅ 公共方法：构建商店 Embed

def build_shop_embed(user_id: str) -> discord.Embed:
    embed = discord.Embed(
        title="🛒 遗迹商店",
        description="**欢迎光临！以下为你的专属商品列表：**",
        color=0x00ffcc,
    )

    for item in shop.list_items_for_user(user_id):
        item_id, name, desc, price, item_type, _, stock = item
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shop_sales WHERE user_id = ? AND item_id = ?", (user_id, item_id))
        count = cursor.fetchone()[0]
        conn.close()
        if item_type == "xp":
            limit_text = f"📦 剩余 {max(0, 10 - count)} 次"
        else:
            limit_text = "♾️ 无限购买"

        embed.add_field(
            name=f"{name}｜💸 {price} 晶核",
            value=f"{desc}\n{limit_text}｜🛒 已购买 {count} 次",
            inline=False,
        )

    return embed

# ✅ 购买按钮
class BuyButton(Button):
    def __init__(self, item_id: int, name: str, disabled: bool):
        super().__init__(label=f"购买 {name}", custom_id=str(item_id), style=discord.ButtonStyle.primary, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        success, msg = await shop.buy_item(user_id, int(self.custom_id), member=interaction.user)
        embed = build_shop_embed(user_id)
        await interaction.message.edit(embed=embed, view=ShopView(user_id))
        await interaction.response.send_message(msg, ephemeral=True)

# ✅ 商店视图
class ShopView(View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.build_buttons()

    def build_buttons(self):
        for item in shop.list_items_for_user(self.user_id):
            item_id, name, _, _, item_type, _, stock = item
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM shop_sales WHERE user_id = ? AND item_id = ?", (self.user_id, item_id))
            count = cursor.fetchone()[0]
            conn.close()
            xp_limit_reached = item_type == "xp" and count >= 10
            disabled = stock == 0 or xp_limit_reached
            self.add_item(BuyButton(item_id, name, disabled))

    @discord.ui.button(label="关闭商店", style=discord.ButtonStyle.danger, row=4)
    async def close(self, interaction: discord.Interaction, button: Button):
        if str(interaction.user.id) != str(self.user_id):
            await interaction.response.send_message("❌ 你无法关闭别人的商店。", ephemeral=True)
        else:
            await interaction.message.delete()

# ✅ 指令注册

def setup_shop_commands(bot: commands.Bot):

    @bot.command()
    async def 商店(ctx):
        embed = build_shop_embed(str(ctx.author.id))
        await ctx.reply(embed=embed, view=ShopView(str(ctx.author.id)), mention_author=False)

    @bot.command()
    async def 购买(ctx, *, 商品名):
        user_id = str(ctx.author.id)
        items = shop.list_items_for_user(user_id)
        for item in items:
            item_id, name, *_ = item
            if name == 商品名:
                success, message = await shop.buy_item(user_id, item_id, member=ctx.author)
                return await ctx.send(message)
        await ctx.send("❌ 未找到该商品，请确认商品名称是否正确。")

    @bot.command()
    async def 我的消费(ctx, 页数: int = 1):
        limit = 10
        offset = (页数 - 1) * limit
        history = shop.get_user_purchase_history(str(ctx.author.id), limit=limit, offset=offset)
        if not history:
            await ctx.send("🔍 没有找到你的消费记录。")
        else:
            embed = discord.Embed(title=f"📒 {ctx.author.display_name} 的消费记录（第 {页数} 页）",
                                  description="\n".join(history),
                                  color=0x55ccaa)
            await ctx.send(embed=embed)

    @bot.command()
    async def 商店统计(ctx):
        if not any(role.id == SHOPADMIN_ROLE_ID for role in ctx.author.roles):
            return await ctx.send("❌ 你没有权限使用此指令。")

        embed = discord.Embed(title="📊 遗迹商店销量统计", color=0x33ccff)
        for item in shop.list_items():
            item_id, name, *_ = item
            stats = shop.get_sales_statistics(item_id)
            embed.add_field(name=name,
                            value=f"总额：{stats['total']}｜周额：{stats['weekly']}｜季额：{stats['season']}",
                            inline=False)
        await ctx.send(embed=embed)
