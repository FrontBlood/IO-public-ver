import asyncio

import discord

from database import avalon_db


METRIC_LABELS = {
    "wins": "胜场",
    "win_rate": "胜率",
    "games": "场次",
}


def build_player_stats_embed(user_id: int | str, display_name: str, stats: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️ {display_name}的阿瓦隆战绩",
        color=0x5865F2,
    )
    embed.add_field(name="胜场", value=str(stats["wins"]), inline=True)
    embed.add_field(name="胜率", value=f'{stats["win_rate"]:.1f}%', inline=True)
    embed.add_field(name="场次", value=str(stats["total_games"]), inline=True)
    embed.add_field(name="梅林胜活", value=str(stats["merlin_survived_wins"]), inline=True)
    embed.add_field(name="刺客刺胜", value=str(stats["assassin_hits"]), inline=True)
    if stats["total_games"] == 0:
        embed.description = "还没有完成过阿瓦隆对局。"
    return embed


def build_leaderboard_embed(metric: str, rows: list[dict]) -> discord.Embed:
    label = METRIC_LABELS[metric]
    embed = discord.Embed(title=f"🏆 阿瓦隆排行 · {label}", color=0xF1C40F)
    if not rows:
        embed.description = "完成 3 局后即可入榜。"
        return embed
    embed.set_footer(text="完成至少 3 局即可入榜")

    medals = ("🥇", "🥈", "🥉")
    lines = []
    for index, row in enumerate(rows):
        place = medals[index] if index < len(medals) else f"{index + 1}."
        lines.append(
            f'{place} <@{row["user_id"]}>\n'
            f'　{row["wins"]} 胜 · {row["win_rate"]:.1f}% · {row["total_games"]} 局'
        )
    embed.description = "\n".join(lines)
    return embed


class AvalonLeaderboardView(discord.ui.View):
    def __init__(self, metric: str = "wins"):
        super().__init__(timeout=300)
        self.metric = metric
        self._sync_buttons()

    def _sync_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = item.custom_id == f"avalon:rank:{self.metric}"

    async def _show(self, interaction: discord.Interaction, metric: str):
        self.metric = metric
        self._sync_buttons()
        rows = await asyncio.to_thread(avalon_db.get_leaderboard, metric)
        await interaction.response.edit_message(
            embed=build_leaderboard_embed(metric, rows),
            view=self,
        )

    @discord.ui.button(label="胜场", style=discord.ButtonStyle.primary, custom_id="avalon:rank:wins")
    async def wins(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show(interaction, "wins")

    @discord.ui.button(label="胜率", style=discord.ButtonStyle.secondary, custom_id="avalon:rank:win_rate")
    async def win_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show(interaction, "win_rate")

    @discord.ui.button(label="场次", style=discord.ButtonStyle.secondary, custom_id="avalon:rank:games")
    async def games(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show(interaction, "games")


async def send_player_stats(ctx, member):
    stats = await asyncio.to_thread(avalon_db.get_player_stats, member.id)
    await ctx.send(embed=build_player_stats_embed(member.id, member.display_name, stats))


async def send_leaderboard(ctx):
    metric = "wins"
    rows = await asyncio.to_thread(avalon_db.get_leaderboard, metric)
    await ctx.send(
        embed=build_leaderboard_embed(metric, rows),
        view=AvalonLeaderboardView(metric),
    )
