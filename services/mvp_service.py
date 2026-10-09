import random
import asyncio
from datetime import datetime

import discord
from discord.ui import View, Button

from database.mvp_dao import (
    init_mvp_tables,
    save_mvp_state,
    get_mvp_state,
    close_mvp_state,
    add_vote,
    get_votes,
    get_unique_voters,
    clear_votes,
)

from services.mvp_image import generate_mvp_image


REFRESH_INTERVAL = 20
mvp_refresh_task = None


# ============================
# 按钮 UI
# ============================
class MVPVoteView(View):
    def __init__(self, candidates):
        super().__init__(timeout=None)
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
                         "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for idx, c in enumerate(candidates):
            num = number_emojis[idx]
            style = discord.ButtonStyle.primary if c["team"] == "A" else discord.ButtonStyle.danger

            btn = Button(
                label=f"{num} {c['name']}",
                style=style,
                custom_id=f"mvp_vote_{c['id']}"
            )
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction):
        return True


# ============================
# 计算并生成图片
# ============================
def build_image_data():
    state = get_mvp_state()
    if not state:
        return None

    candidates = state["candidates"]
    votes_raw = get_votes()

    vote_count = {str(c["id"]): 0 for c in candidates}
    for _, cid in votes_raw:
        cid = str(cid)
        if cid in vote_count:
            vote_count[cid] += 1

    teamA = sorted(
        [c for c in candidates if c["team"] == "A"],
        key=lambda c: vote_count[str(c["id"])],
        reverse=True
    )
    teamB = sorted(
        [c for c in candidates if c["team"] == "B"],
        key=lambda c: vote_count[str(c["id"])],
        reverse=True
    )

    blue_data = [(c["name"], vote_count[str(c["id"])]) for c in teamA]
    red_data = [(c["name"], vote_count[str(c["id"])]) for c in teamB]

    return {
        "blue_team": blue_data,
        "red_team": red_data,
        "blue_name": teamA[0]["team_name"],
        "red_name": teamB[0]["team_name"],
    }


# ============================
# 刷新任务
# ============================
async def refresh_mvp_loop(bot):
    await bot.wait_until_ready()

    while True:
        state = get_mvp_state()
        if not state or not state["is_open"]:
            return

        try:
            channel = bot.get_channel(int(state["channel_id"]))
            msg = await channel.fetch_message(int(state["message_id"]))

            data = build_image_data()
            if data:
                generate_mvp_image(
                    blue_team=data["blue_team"],
                    red_team=data["red_team"],
                    blue_name=data["blue_name"],
                    red_name=data["red_name"],
                    output_path="mvp.png",
                    final=False
                )

                file = discord.File("mvp.png", filename="mvp.png")
                embed = discord.Embed(
                    title="🏆 MVP 投票（进行中）",
                    description=f"⏱️ 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    color=0x00AFFE
                )
                embed.set_image(url="attachment://mvp.png")

                await msg.edit(embed=embed, attachments=[file])

        except Exception as e:
            print(f"[MVP] 刷新错误: {e}")

        await asyncio.sleep(REFRESH_INTERVAL)


# ============================
# 开启投票
# ============================
async def start_mvp_vote(bot, channel, candidates):
    init_mvp_tables()
    clear_votes()

    view = MVPVoteView(candidates)
    embed = discord.Embed(
        title="🏆 MVP 投票开始！",
        description="点击下方按钮投票！",
        color=0x00AFFE
    )

    msg = await channel.send(embed=embed, view=view)

    save_mvp_state(str(msg.id), str(channel.id), candidates)

    global mvp_refresh_task
    if mvp_refresh_task:
        mvp_refresh_task.cancel()

    mvp_refresh_task = bot.loop.create_task(refresh_mvp_loop(bot))


# ============================
# 投票处理
# ============================
async def handle_vote(interaction: discord.Interaction):
    cid = interaction.data["custom_id"].split("_")[-1]
    add_vote(str(interaction.user.id), str(cid))

    await interaction.response.send_message(
        f"你已投票给 <@{cid}>！",
        ephemeral=True
    )


# ============================
# 关闭投票
# ============================
async def close_mvp(bot):
    state = get_mvp_state()
    if not state:
        return "当前没有正在进行的投票。"

    close_mvp_state()

    channel = bot.get_channel(int(state["channel_id"]))
    msg = await channel.fetch_message(int(state["message_id"]))

    data = build_image_data()

    # 图片最终版
    generate_mvp_image(
        blue_team=data["blue_team"],
        red_team=data["red_team"],
        blue_name=data["blue_name"],
        red_name=data["red_name"],
        output_path="mvp.png",
        final=True
    )

    # MVP 计算
    votes_raw = get_votes()
    vote_count = {}

    for _, cid in votes_raw:
        cid = str(cid)
        vote_count[cid] = vote_count.get(cid, 0) + 1

    max_votes = max(vote_count.values()) if vote_count else 0
    mvps = [cid for cid, v in vote_count.items() if v == max_votes]

    if max_votes == 0:
        mvp_text = "无人投票"
    else:
        mvp_text = "、".join([f"<@{cid}>" for cid in mvps]) + f"（{max_votes}票）"

    lucky_pool = get_unique_voters()
    lucky_text = f"<@{random.choice(lucky_pool)}>" if lucky_pool else "无人参与"

    file = discord.File("mvp.png", filename="mvp.png")
    
    embed = discord.Embed(
        title="🏁 MVP 投票已结束",
        description=f"⏱️ 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        color=0xFFD700
    )

    # 让图片绝对显示在最上方
    embed.set_image(url="attachment://mvp.png")

    # 所有文字内容必须放到 field
    embed.add_field(name="🏆 本场 MVP", value=mvp_text, inline=False)
    embed.add_field(name="🎉 幸运观众", value=lucky_text, inline=False)

    await msg.edit(embed=embed, attachments=[file], view=None)
    return "投票已关闭"
