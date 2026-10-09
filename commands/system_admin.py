import asyncio
import os

from discord.ext import commands

from config.constants import CHECKIN_EVENT_ADMIN_USER_ID, NEWBEEMANAGER_ROLE_ID


def _can_restart(ctx: commands.Context) -> bool:
    author = ctx.author
    if author.id == CHECKIN_EVENT_ADMIN_USER_ID:
        return True
    return any(role.id == NEWBEEMANAGER_ROLE_ID for role in getattr(author, "roles", []))


def setup(bot: commands.Bot):
    @bot.command(name="重启艾欧")
    async def restart_aiou(ctx: commands.Context):
        if not _can_restart(ctx):
            return

        await ctx.reply("正在重启艾欧。", mention_author=False)
        await asyncio.sleep(1)
        os._exit(1)
