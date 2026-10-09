import asyncio
import sqlite3
from datetime import date
from pathlib import Path

import discord
from discord.ext import commands

from tools.user_activity_report import build_report


def _change(value: float | None) -> str:
    if value is None:
        return "无可比数据"
    arrow = "↑" if value > 0 else "↓" if value < 0 else "→"
    return f"{arrow} {abs(value):.1%}"


def build_weekly_embed(report: dict) -> discord.Embed:
    current = report["current"]
    previous = report["previous"]
    retention = report["retention"]
    comparison = report["comparison"]
    wau_change = comparison["wau"]["change_rate"]
    color = discord.Color.green() if wau_change is not None and wau_change >= 0 else discord.Color.orange()
    embed = discord.Embed(
        title="服务器用户活跃与留存周报",
        description=(f"统计周期：`{current['start']}` ～ `{current['end']}`（UTC）\n"
                     f"对比周期：`{previous['start']}` ～ `{previous['end']}`"),
        color=color,
    )
    embed.add_field(
        name="整体活跃",
        value=(f"**WAU：{current['wau']:,}**（{_change(comparison['wau']['change_rate'])}）\n"
               f"平均 DAU：{current['avg_dau']:,.1f}（{_change(comparison['avg_dau']['change_rate'])}）\n"
               f"峰值 DAU：{current['peak_dau']:,}\n活跃粘性：{current['stickiness']:.1%}"),
        inline=True,
    )
    embed.add_field(
        name="留存与流动",
        value=(f"周留存：**{retention['week_over_week_retention']:.1%}**\n"
               f"留存：{retention['retained_users']:,}｜新增：{retention['new_active_users']:,}\n"
               f"回流：{retention['resurrected_users']:,}｜流失：{retention['churned_users']:,}"),
        inline=True,
    )
    channel_users, channel_xp = current["channel_users"], current["channel_xp"]
    embed.add_field(
        name="行为构成",
        value=(f"文字：{channel_users.get('text', 0):,} 人｜{channel_xp.get('text', 0):,} XP\n"
               f"语音：{channel_users.get('voice', 0):,} 人｜{channel_xp.get('voice', 0):,} XP\n"
               f"直播：{channel_users.get('stream', 0):,} 人｜{channel_xp.get('stream', 0):,} XP\n"
               f"总 XP：{current['total_xp']:,}（{_change(comparison['total_xp']['change_rate'])}）"),
        inline=False,
    )
    if wau_change is not None and wau_change <= -0.1:
        assessment = "本周活跃明显回落，建议检查主要频道活动安排，并对上周流失用户做定向召回。"
    elif wau_change is not None and wau_change >= 0.1:
        assessment = "本周活跃明显增长，建议复盘带来新增和回流的活动或频道。"
    else:
        assessment = "本周整体活跃基本稳定，建议继续观察留存和各行为渠道的变化。"
    embed.add_field(name="服务器评估", value=assessment, inline=False)
    freshness = f"数据覆盖：{report['source_coverage']['first']} ～ {report['source_coverage']['latest']}"
    if report.get("excluded_partial_day"):
        freshness += f"；已排除疑似未完结日 {report['excluded_partial_day']}"
    embed.set_footer(text=f"{freshness}｜活跃口径：当日获得文字/语音/直播 XP")
    return embed


def setup(bot: commands.Bot):
    @bot.command(name="周报", aliases=["活跃周报", "weekly"])
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def user_activity_weekly(ctx: commands.Context, end_date: str | None = None):
        """用法：&周报 或 &周报 2026-05-18。"""
        requested_end = None
        if end_date:
            try:
                requested_end = date.fromisoformat(end_date)
            except ValueError:
                return await ctx.reply("日期格式不正确。请使用 `&周报 YYYY-MM-DD`，例如 `&周报 2026-05-18`。", mention_author=False)
        async with ctx.typing():
            try:
                report = await asyncio.to_thread(build_report, Path("levels.db"), requested_end, True)
            except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
                return await ctx.reply(f"周报生成失败：`{str(exc)[:300]}`", mention_author=False)
        await ctx.reply(embed=build_weekly_embed(report), mention_author=False)

    @user_activity_weekly.error
    async def user_activity_weekly_error(ctx: commands.Context, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"周报正在冷却，请等待 {error.retry_after:.0f} 秒后再试。", mention_author=False)
            return
        if isinstance(error, commands.TooManyArguments):
            await ctx.reply("用法：`&周报` 或 `&周报 YYYY-MM-DD`。", mention_author=False)
            return
        raise error
