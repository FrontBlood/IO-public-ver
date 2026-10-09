import asyncio
from datetime import datetime, timedelta

from discord.ext import tasks
from discord import Embed
from database.dao_user import get_or_create_user, update_user
from database.daily_limit import can_gain_xp
from services.xp_tracker import apply_xp_and_check_level, decay_inactive_users, get_level_from_xp
from services.role_utils import check_level_change, needs_level_role_sync
from config.constants import ANNOUNCE_CHANNEL_ID

@tasks.loop(minutes=1)
async def distribute_voice_and_stream_xp(bot):
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot:
                    continue
                user = get_or_create_user(str(member.id))

                # 记录本轮初始等级
                text_level_before = get_level_from_xp("text", user.text_xp)
                voice_level_before = get_level_from_xp("voice", user.voice_xp)
                stream_level_before = get_level_from_xp("stream", user.stream_xp)

                # 语音经验（所有人均得）
                if not member.voice.self_deaf and not member.voice.deaf:
                    if can_gain_xp(user.user_id, "voice", 9):
                        leveled_up, user = await apply_xp_and_check_level(user, "voice", 8, member=member)
                        if leveled_up or needs_level_role_sync(member, user):
                            update_user(user)
                            await check_level_change(member, user)

                            level_up_channel = guild.get_channel(ANNOUNCE_CHANNEL_ID)
                            if leveled_up and level_up_channel:
                                total_level = get_level_from_xp("text", user.text_xp) + get_level_from_xp("voice", user.voice_xp) + get_level_from_xp("stream", user.stream_xp)
                                try:
                                    from services.mengmeng_service import grant_level_reward_if_eligible
                                    grant_level_reward_if_eligible(str(member.id), total_level)
                                except Exception:
                                    pass
                                embed = Embed(
                                    title="🎉 等级提升！",
                                    description=(
                                        f"{member.mention} 在「语音活跃」中等级提升！\n\n"
                                        f"🏅 当前遗迹等级：**Lv.{total_level}**"
                                    ),
                                    color=0x00ff99
                                )
                                embed.set_thumbnail(url=member.display_avatar.url)
                                await level_up_channel.send(embed=embed)
                                
                # 直播经验（正在开播者额外得）
                if member.voice and member.voice.self_stream:
                    if not member.voice.self_deaf and not member.voice.deaf:
                        if can_gain_xp(user.user_id, "stream", 34):
                            leveled_up, user = await apply_xp_and_check_level(user, "stream", 33, member=member)
                            if leveled_up or needs_level_role_sync(member, user):
                                update_user(user)
                                await check_level_change(member, user)

                                level_up_channel = guild.get_channel(ANNOUNCE_CHANNEL_ID)
                                if leveled_up and level_up_channel:
                                    total_level = get_level_from_xp("text", user.text_xp) + get_level_from_xp("voice", user.voice_xp) + get_level_from_xp("stream", user.stream_xp)
                                    try:
                                        from services.mengmeng_service import grant_level_reward_if_eligible
                                        grant_level_reward_if_eligible(str(member.id), total_level)
                                    except Exception:
                                        pass
                                    embed = Embed(
                                        title="🎉 等级提升！",
                                        description=(
                                            f"{member.mention} 在「直播活跃」中等级提升！\n\n"
                                            f"🏅 当前遗迹等级：**Lv.{total_level}**"
                                        ),
                                        color=0x00ffcc
                                    )
                                    embed.set_thumbnail(url=member.display_avatar.url)
                                    await level_up_channel.send(embed=embed)
                                    
                # 统一在经验处理后再保存一次（非leveled_up也保存，保证活跃时间更新）
                update_user(user)

            try:
                from services.mengmeng_voice_runtime import voice_tick_async
                await voice_tick_async(bot, vc, interval_seconds=60)
            except Exception:
                pass

def start_periodic_tasks(bot):
    distribute_voice_and_stream_xp.start(bot)


async def scheduled_decay_loop(bot, hour: int, minute: int):
    await bot.wait_until_ready()
    print(f"[Decay] Scheduler started, next run is daily at {hour:02d}:{minute:02d}")

    while True:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if target <= now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        print(f"[Decay] Next decay run in {wait_seconds / 3600:.2f} hours")
        await asyncio.sleep(wait_seconds)

        try:
            await decay_inactive_users(bot)
            print("[Decay] Daily decay run completed")
        except Exception as exc:
            print(f"[Decay] Daily decay run failed: {exc}")


def start_decay_loop(bot, hour=5, minute=0):
    existing_task = getattr(bot, "_daily_decay_task", None)
    if existing_task and not existing_task.done():
        return

    bot._daily_decay_task = bot.loop.create_task(scheduled_decay_loop(bot, hour, minute))
