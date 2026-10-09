import asyncio

import discord
from discord.ext import commands

from config.constants import (
    DEBUG_CHANNEL_ID,
    NEWBEEMANAGER_ROLE_ID,
    PRIVATE_ROOM_ACTIVE_CATEGORY_ID,
)


PEEK_ROLE_ID = NEWBEEMANAGER_ROLE_ID
REQUIRED_ROLE_ID = NEWBEEMANAGER_ROLE_ID
TS_CHANNEL_ID = DEBUG_CHANNEL_ID


def setup(bot: commands.Bot):
    @bot.command(name="TS")
    async def temp_spectate(ctx: commands.Context):
        if ctx.channel.id != TS_CHANNEL_ID:
            return

        guild = ctx.guild
        author = ctx.author

        required_role = guild.get_role(REQUIRED_ROLE_ID)
        if required_role not in author.roles:
            return

        category = guild.get_channel(PRIVATE_ROOM_ACTIVE_CATEGORY_ID)
        peek_role = guild.get_role(PEEK_ROLE_ID)

        if not isinstance(category, discord.CategoryChannel) or peek_role is None:
            await author.send("❌ 私房分类ID或透视身份组配置错误，请联系管理员。")
            return

        overwrite = discord.PermissionOverwrite()
        overwrite.view_channel = True
        overwrite.connect = False
        overwrite.speak = False
        overwrite.stream = False
        overwrite.use_voice_activation = False

        affected = 0
        for channel in category.channels:
            if isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(
                    peek_role,
                    overwrite=overwrite,
                    reason="临时透视",
                )
                affected += 1

        await author.send(
            f"👁️ **临时透视已开启**\n"
            f"⏱️ 时长：60秒\n"
            f"📡 影响语音频道数：{affected}"
        )

        await asyncio.sleep(60)

        for channel in category.channels:
            if isinstance(channel, discord.VoiceChannel):
                try:
                    await channel.set_permissions(
                        peek_role,
                        overwrite=None,
                        reason="透视到期",
                    )
                except Exception:
                    pass

        await author.send("🕒 **透视已到期，权限已移除。**")
