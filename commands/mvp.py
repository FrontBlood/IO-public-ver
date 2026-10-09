import discord
from discord.ext import commands

from services.mvp_service import (
    start_mvp_vote,
    close_mvp,
    handle_vote,
)

class MVPCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mvp")
    @commands.has_role(0)
    async def mvp(self, ctx, *args):
        """
        用法：
        &mvp @1 @2 @3 @4 @5 @6 @7 @8 @9 @10 TeamA TeamB
        """

        if len(args) < 12:
            await ctx.send("❌ 需要 10 名成员 + 2 个队名。")
            return

        member_args = args[:10]
        teamA_name = args[10]
        teamB_name = args[11]

        # 解析成员
        members = []
        for a in member_args:
            try:
                m = await commands.MemberConverter().convert(ctx, a)
                members.append(m)
            except:
                await ctx.send(f"❌ 无法识别成员：{a}")
                return

        if len(members) != 10:
            await ctx.send("❌ 必须严格指定 10 名成员。")
            return

        # 分队
        candidates = []
        for i, m in enumerate(members):
            team = "A" if i < 5 else "B"
            candidates.append({
                "id": str(m.id),
                "name": m.display_name,
                "team": team,
                "team_name": teamA_name if team == "A" else teamB_name
            })

        # 启动投票
        await start_mvp_vote(self.bot, ctx.channel, candidates)

    @commands.command(name="mvpclose")
    @commands.has_role(0)
    async def mvpclose(self, ctx):
        msg = await close_mvp(self.bot)
        await ctx.send(msg)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            cid = interaction.data.get("custom_id", "")
            if cid.startswith("mvp_vote_"):
                await handle_vote(interaction)


async def setup(bot):
    await bot.add_cog(MVPCommands(bot))
