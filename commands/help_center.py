from dataclasses import dataclass

import discord
from discord.ext import commands

from config.constants import NEWBEEMANAGER_ROLE_ID


@dataclass(frozen=True)
class HelpEntry:
    usage: str
    description: str


PUBLIC_ENTRIES = [
    HelpEntry("&rank", "查看等级"),
    HelpEntry("&签到", "每日签到"),
    HelpEntry("&签到天数", "查看连续签到"),
    HelpEntry("&签到排行", "查看签到排行"),
    HelpEntry("&签到纪录榜", "查看历史签到纪录"),
    HelpEntry("&成就", "查看成就进度"),
    HelpEntry("&晶核余额", "查看晶核余额"),
    HelpEntry("&兑换晶核 类型 数量", "经验兑换晶核"),
    HelpEntry("&转账晶核 @成员 数量", "转账晶核"),
    HelpEntry("&商店", "打开商店"),
    HelpEntry("&购买 商品名", "购买商品"),
    HelpEntry("&我的消费 [页数]", "查看消费记录"),
]


MANAGER_ENTRIES = [
    HelpEntry("&newbee 天数", "查看新成员"),
    HelpEntry("&nbcheck", "查看上次 newbee 时间"),
    HelpEntry("&nbtag @成员...", "发放萌新标签"),
    HelpEntry("&等级组巡检", "巡检等级身份组"),
    HelpEntry("&私房巡检", "巡检私房状态"),
    HelpEntry("&TS", "开启私房透视"),
    HelpEntry("&开启掉落", "开启掉落"),
    HelpEntry("&关闭掉落", "关闭掉落"),
    HelpEntry("&掉落统计", "查看掉落统计"),
    HelpEntry("&设置掉落比例 百分比", "设置掉落比例"),
    HelpEntry("&设置掉落数量 数量", "设置掉落数量"),
    HelpEntry("&设置掉落周期 分钟", "设置掉落周期"),
    HelpEntry("&商店统计", "查看商店统计"),
]


ADMIN_ENTRIES = [
    HelpEntry("&exp @成员 类型 数量", "增加经验"),
    HelpEntry("&dexp @成员 类型 数量", "减少经验"),
    HelpEntry("&ranrank [人数]", "查看等级排行"),
    HelpEntry("&sprank", "查看等级分布"),
    HelpEntry("&lastlive @成员", "查看最后活跃"),
    HelpEntry("&inactive @成员", "查看不活跃天数"),
    HelpEntry("&增加晶核 @成员 数量", "增加晶核"),
    HelpEntry("&减少晶核 @成员 数量", "扣除晶核"),
    HelpEntry("&重置成就记录 [@成员]", "重置成就状态"),
    HelpEntry("&清空成就记录 [@成员]", "清空成就记录"),
]


def _is_admin(ctx: commands.Context) -> bool:
    return bool(ctx.author.guild_permissions.administrator)


def _is_manager(ctx: commands.Context) -> bool:
    return any(role.id == NEWBEEMANAGER_ROLE_ID for role in ctx.author.roles)


def _chunk_two_columns(entries: list[HelpEntry]) -> tuple[list[HelpEntry], list[HelpEntry]]:
    midpoint = (len(entries) + 1) // 2
    return entries[:midpoint], entries[midpoint:]


def _render_entries(entries: list[HelpEntry]) -> str:
    return "\n\n".join(f"`{entry.usage}`\n{entry.description}" for entry in entries)


def build_help_embed(ctx: commands.Context) -> discord.Embed:
    if _is_admin(ctx):
        title = "管理员指令"
        color = 0xE74C3C
        entries = MANAGER_ENTRIES + ADMIN_ENTRIES
    elif _is_manager(ctx):
        title = "管理指令"
        color = 0xF39C12
        entries = MANAGER_ENTRIES
    else:
        title = "常用指令"
        color = 0x5DADE2
        entries = PUBLIC_ENTRIES

    left, right = _chunk_two_columns(entries)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="指令", value=_render_entries(left)[:1024] or "无", inline=True)
    embed.add_field(name="指令", value=_render_entries(right)[:1024] or "无", inline=True)
    return embed


def setup(bot):
    @bot.command(name="帮助", aliases=["菜单"])
    async def help_center(ctx: commands.Context):
        await ctx.send(embed=build_help_embed(ctx))
