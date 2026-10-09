# commands/achievement_commands.py

from discord.ext import commands
from discord import Embed
from services.achievement_engine import check_and_unlock_achievements, build_achievement_summary
from database.achievement_dao import get_unlocked_achievement_ids, reset_user_achievements, clear_user_achievements, generate_progress_bar
from database.dao_user import get_or_create_user


def setup(bot):
    @bot.command(name="成就")
    async def achievement_command(ctx):
        user_id = str(ctx.author.id)
        user = get_or_create_user(user_id)

        unlocked_before = set(get_unlocked_achievement_ids(user_id))
        await check_and_unlock_achievements(user_id, member=ctx.author)
        unlocked_after = set(get_unlocked_achievement_ids(user_id))
        unlocked_now_ids = unlocked_after - unlocked_before

        display = build_achievement_summary(user_id, user, unlocked_after)

        embed = Embed(
            title="📜 本次成就达成情况",
            description=f"{ctx.author.mention}，以下是你本次新达成的成就，以及仍在进行中的成就：",
            color=0x33cccc
        )

        for ach in display:
            is_done = ach["unlocked"]

            if ach["id"] in unlocked_now_ids:
                prefix = "<a:GreenCheck:0>"
                status = "已完成"
            elif not is_done:
                prefix = "<a:Pinkstargif:0>"
                status = "未完成"
            else:
                continue

            try:
                current, total = map(int, ach["progress"].split("/")[:2])
            except:
                current, total = 0, 1

            progress_bar, percent_text = generate_progress_bar(current, total)

            reward_str = []
            if "core" in ach["rewards"]:
                reward_str.append(f"{ach['rewards']['core']} 晶核")
            if "xp" in ach["rewards"]:
                xp = ach["rewards"]["xp"]
                reward_str.extend([f"+{v} {k} exp" for k, v in xp.items()])

            embed.add_field(
                name=f"{prefix} {ach['name']}（{status}）",
                value=(
                    f"{ach['description']}\n"
                    f"<:__2:0> 进度：`{current} / {total}`\n"
                    f"{progress_bar}（{percent_text}）\n"
                    f"<:59794giveaways:0> 奖励：{' | '.join(reward_str) if reward_str else '无'}\n\n\n"
                ),
                inline=False
            )

        await ctx.reply(embed=embed, mention_author=True)

        
    @bot.command(name="重置成就记录")
    @commands.has_permissions(administrator=True)
    async def reset_achievements(ctx, member: commands.MemberConverter = None):
        member = member or ctx.author
        reset_user_achievements(str(member.id))
        await ctx.send(f"🔄 {member.mention} 的成就状态已重置为未解锁。")

    @bot.command(name="清空成就记录")
    @commands.has_permissions(administrator=True)
    async def clear_achievements(ctx, member: commands.MemberConverter = None):
        member = member or ctx.author
        clear_user_achievements(str(member.id))
        await ctx.send(f"🗑️ {member.mention} 的所有成就记录已清除。")
