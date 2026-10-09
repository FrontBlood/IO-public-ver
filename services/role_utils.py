import asyncio

import discord
from discord.ext import commands

from config.constants import DEBUG_CHANNEL_ID
from config.level_roles import LEVEL_ROLE_MAP
from database.dao_user import get_or_create_user
from database.role_sync_jobs import (
    delete_role_sync_job,
    get_incomplete_role_sync_jobs,
    get_role_sync_job,
    update_role_sync_job_status,
    upsert_role_sync_job,
)
from services.xp_tracker import get_level_from_xp


ROLE_SYNC_LOCKS: dict[str, asyncio.Lock] = {}


def _lock_key(guild_id: int | str, user_id: int | str) -> str:
    return f"{guild_id}:{user_id}"


def get_role_sync_lock(guild_id: int | str, user_id: int | str) -> asyncio.Lock:
    key = _lock_key(guild_id, user_id)
    lock = ROLE_SYNC_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        ROLE_SYNC_LOCKS[key] = lock
    return lock


def get_expected_level_role(guild: discord.Guild, user):
    text_level = get_level_from_xp("text", user.text_xp)
    voice_level = get_level_from_xp("voice", user.voice_xp)
    stream_level = get_level_from_xp("stream", user.stream_xp)
    total_level = text_level + voice_level + stream_level

    target_role = None
    for lvl, _name, role_id in sorted(LEVEL_ROLE_MAP, reverse=True):
        if total_level >= lvl and role_id:
            target_role = guild.get_role(role_id)
            break

    return target_role, total_level


def needs_level_role_sync(member: discord.Member, user=None) -> bool:
    user = user or get_or_create_user(str(member.id))
    target_role, total_level = get_expected_level_role(member.guild, user)
    level_role_ids = {role_id for _, _, role_id in LEVEL_ROLE_MAP if role_id}
    current_level_role_ids = {role.id for role in member.roles if role.id in level_role_ids}

    if total_level <= 0:
        return bool(current_level_role_ids)

    if target_role is None:
        return False

    return current_level_role_ids != {target_role.id}


async def _execute_role_sync_job(member: discord.Member, job: dict) -> bool:
    guild = member.guild
    guild_id = str(guild.id)
    user_id = str(member.id)
    target_role = guild.get_role(job["target_role_id"]) if job["target_role_id"] else None
    roles_to_remove = [role for role in member.roles if role.id in set(job["roles_to_remove"])]
    already_has_target = target_role in member.roles if target_role else False

    if job["target_role_id"] and target_role is None:
        update_role_sync_job_status(
            guild_id,
            user_id,
            "failed",
            last_error="target_role_missing",
            increment_attempt=True,
        )
        return False

    try:
        update_role_sync_job_status(
            guild_id,
            user_id,
            "removing",
            last_error="",
            increment_attempt=True,
        )

        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="等级身份组更新")

        update_role_sync_job_status(guild_id, user_id, "adding", last_error="")

        if target_role and not already_has_target:
            await member.add_roles(target_role, reason="等级身份组更新")

            channel = guild.get_channel(DEBUG_CHANNEL_ID)
            if channel:
                await channel.send(
                    f"{member.mention} 的身份组已更新，现在是 **{target_role.name}**"
                )

        delete_role_sync_job(guild_id, user_id)
        return True
    except discord.Forbidden:
        update_role_sync_job_status(
            guild_id,
            user_id,
            "failed",
            last_error="forbidden",
        )
        print(f"无法修改 {member.display_name} 的身份组，权限不足")
    except discord.HTTPException as exc:
        update_role_sync_job_status(
            guild_id,
            user_id,
            "failed",
            last_error=f"http:{exc.status}",
        )
    except Exception as exc:
        update_role_sync_job_status(
            guild_id,
            user_id,
            "failed",
            last_error=str(exc)[:200],
        )
    return False


async def check_level_change(member: discord.Member, user=None):
    guild = member.guild
    guild_id = str(guild.id)
    user_id = str(member.id)

    user = get_or_create_user(user_id)
    target_role, total_level = get_expected_level_role(guild, user)

    level_role_ids = {role_id for _, _, role_id in LEVEL_ROLE_MAP if role_id}
    current_roles = set(member.roles)
    level_roles_to_remove = [
        role for role in current_roles
        if role.id in level_role_ids and (target_role is None or role.id != target_role.id)
    ]
    already_has_target = target_role in current_roles if target_role else False

    if not target_role and total_level > 0:
        return

    if not level_roles_to_remove and (not target_role or already_has_target):
        delete_role_sync_job(guild_id, user_id)
        return

    async with get_role_sync_lock(guild_id, user_id):
        upsert_role_sync_job(
            guild_id,
            user_id,
            target_role.id if target_role else None,
            [role.id for role in level_roles_to_remove],
        )
        job = get_role_sync_job(guild_id, user_id)
        if job:
            await _execute_role_sync_job(member, job)


async def resume_pending_role_sync_jobs(bot, limit: int = 50):
    jobs = get_incomplete_role_sync_jobs(limit=limit)
    for job in jobs:
        guild = bot.get_guild(int(job["guild_id"]))
        member = guild.get_member(int(job["user_id"])) if guild else None
        if member is None:
            update_role_sync_job_status(
                job["guild_id"],
                job["user_id"],
                "failed",
                last_error="member_not_found",
            )
            continue

        async with get_role_sync_lock(job["guild_id"], job["user_id"]):
            fresh_job = get_role_sync_job(job["guild_id"], job["user_id"])
            if fresh_job:
                await _execute_role_sync_job(member, fresh_job)
                await asyncio.sleep(0.2)


async def pending_role_sync_recovery_loop(bot):
    await bot.wait_until_ready()
    await resume_pending_role_sync_jobs(bot)

    while True:
        await asyncio.sleep(300)
        await resume_pending_role_sync_jobs(bot)


def start_role_sync_recovery_loop(bot):
    existing_task = getattr(bot, "_role_sync_recovery_task", None)
    if existing_task and not existing_task.done():
        return
    bot._role_sync_recovery_task = bot.loop.create_task(pending_role_sync_recovery_loop(bot))


def has_role_by_id(role_id: int):
    def predicate(ctx):
        return any(role.id == role_id for role in ctx.author.roles)
    return commands.check(predicate)
