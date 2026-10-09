from services.role_utils import (
    check_level_change,
    needs_level_role_sync,
    start_role_sync_recovery_loop,
)
from database.dao_user import get_or_create_user, update_user
from database.daily_limit import can_gain_xp
from services.xp_tracker import apply_xp_and_check_level, get_level_from_xp
from config.constants import ANNOUNCE_CHANNEL_ID
from config.moderation_config import SCAM_IMAGE_GUARD_ENABLED
from discord.ext import tasks
from services.voice_stream_tasks import start_periodic_tasks, start_decay_loop
import discord
from services.temp_role_checker import start_temp_role_checker
from commands import mengmeng_commands
from services.mention_guard_services import should_delete_for_mentions
from services.image_scam_moderation import (
    has_image_attachment,
    log_scam_image_guard_status,
    moderate_image_message_later,
)
from services.private_room_manager import (
    handle_private_room_voice_state_update,
    rollback_private_room_manage_channels_if_needed,
    sync_private_room_records,
    start_private_room_sweep_loop,
)


def register_events(bot, decay_hour=5, decay_minute=0):
    @bot.event
    async def on_ready():        
        start_periodic_tasks(bot)
        start_decay_loop(bot, hour=decay_hour, minute=decay_minute)
        start_role_sync_recovery_loop(bot)
        log_scam_image_guard_status()
        private_room_summary = sync_private_room_records(bot)
        print(
            "[PrivateRoom] Records synced: "
            f"guilds={private_room_summary['guild_count']}, "
            f"channels={private_room_summary['managed_channels']}, "
            f"created={private_room_summary['created_records']}"
        )
        start_private_room_sweep_loop(bot)
        start_temp_role_checker(bot)
        if not bot.get_cog("MengmengCommands"):
            await mengmeng_commands.add_cog_on_ready(bot)
        print(f"✅ Bot 已上线：{bot.user}")

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return

        delete, _reason = should_delete_for_mentions(message)
        if delete:
            try:
                await message.delete()
                return
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return
            except Exception:
                return

        if SCAM_IMAGE_GUARD_ENABLED and has_image_attachment(message):
            bot.loop.create_task(moderate_image_message_later(message))

        await process_message(message)
        await bot.process_commands(message)

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.bot:
            return
        await handle_private_room_voice_state_update(member, before, after)

    @bot.event
    async def on_guild_channel_update(before, after):
        await rollback_private_room_manage_channels_if_needed(before, after)
        if before.name != after.name:
            if "水经验" in after.name:
                try:
                    await after.edit(name=before.name, reason="检测到水经验关键词，自动还原")
                    print(f"⚠️ 检测到水经验关键词，已将频道 {after.id} 名称改回 {before.name}")
                except Exception as e:
                    print(f"❌ 无法更改频道名: {e}")

async def process_message(message, level_up_channel_id=None):
    if message.author.bot:
        return

    content = message.content.strip()
    if len(content) < 5 or content.startswith(("&", "!")):
        return

    user_id = str(message.author.id)
    if not content or not can_gain_xp(user_id, "text", 100):
        return

    user = get_or_create_user(user_id)
    leveled_up, user = await apply_xp_and_check_level(user, "text", 100, member=message.author)
    update_user(user)

    if leveled_up or needs_level_role_sync(message.author, user):
        await check_level_change(message.author, user)

        level_up_channel = message.guild.get_channel(ANNOUNCE_CHANNEL_ID)
        if leveled_up and level_up_channel:
            text_level = get_level_from_xp("text", user.text_xp)
            voice_level = get_level_from_xp("voice", user.voice_xp)
            stream_level = get_level_from_xp("stream", user.stream_xp)
            total_level = text_level + voice_level + stream_level
            try:
                from services.mengmeng_service import grant_level_reward_if_eligible
                grant_level_reward_if_eligible(str(message.author.id), total_level)
            except Exception:
                pass
            embed = discord.Embed(
                title="🎉 等级提升！",
                description=(
                    f"{message.author.mention} 在「文字活跃」中达成了等级提升！\n\n"
                    f"🏅 当前总等级：**Lv.{total_level}**"
                ),
                color=0x00ff99
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            await level_up_channel.send(embed=embed)
