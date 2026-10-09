import discord
from discord.ext import commands

from config.constants import COMMUNITY_MANAGER_ROLE_ID, MESSAGE_DELETE_COMMAND_CHANNEL_ID


def _has_community_manager_role(member: discord.Member) -> bool:
    return any(role.id == COMMUNITY_MANAGER_ROLE_ID for role in member.roles)


async def _find_message_by_id(guild: discord.Guild, message_id: int):
    channels = list(guild.text_channels) + list(guild.threads)
    for channel in channels:
        permissions = channel.permissions_for(guild.me)
        if not permissions.read_message_history:
            continue
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            continue
        except (discord.Forbidden, discord.HTTPException):
            continue
    return None


def setup(bot: commands.Bot):
    @bot.command(name="删消息")
    async def delete_message(ctx: commands.Context, message_id: str):
        if ctx.channel.id != MESSAGE_DELETE_COMMAND_CHANNEL_ID:
            return
        if not isinstance(ctx.author, discord.Member) or not _has_community_manager_role(ctx.author):
            await ctx.reply("你没有权限使用这个指令。", mention_author=False)
            return
        if not ctx.guild:
            return
        if not message_id.isdigit():
            await ctx.reply("用法：`&删消息 消息ID`", mention_author=False)
            return

        target = await _find_message_by_id(ctx.guild, int(message_id))
        if target is None:
            await ctx.reply("未找到这条消息，或机器人没有权限读取对应频道。", mention_author=False)
            return

        try:
            reason = f"message delete command by {ctx.author} ({ctx.author.id})"
            try:
                await target.delete(reason=reason)
            except TypeError:
                await target.delete()
        except discord.Forbidden:
            await ctx.reply("机器人没有权限删除这条消息。", mention_author=False)
            return
        except discord.HTTPException as exc:
            await ctx.reply(f"删除失败：{type(exc).__name__}", mention_author=False)
            return
        await ctx.reply(
            f"已删除消息 `{message_id}`，来源频道：<#{target.channel.id}>。",
            mention_author=False,
        )
