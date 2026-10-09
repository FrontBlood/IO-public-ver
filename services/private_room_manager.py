import asyncio
from datetime import datetime, timedelta, timezone

import discord

from config.constants import (
    PRIVATE_ROOM_ACTIVE_CATEGORY_ID,
    PRIVATE_ROOM_INACTIVE_CATEGORY_ID,
    PRIVATE_ROOM_INACTIVITY_DAYS,
    PRIVATE_ROOM_SWEEP_HOUR,
    PRIVATE_ROOM_SWEEP_MINUTE,
    PRIVATE_ROOM_MANAGE_CHANNELS_GUARD_ENABLED,
)
from database.private_room_state import (
    clear_private_room_empty,
    ensure_private_room_record,
    get_private_room_state,
    mark_private_room_empty,
)


_guild_move_locks: dict[int, asyncio.Lock] = {}


def is_managed_private_room(channel: discord.abc.GuildChannel | None) -> bool:
    if not isinstance(channel, discord.VoiceChannel):
        return False
    return channel.category_id in {
        PRIVATE_ROOM_ACTIVE_CATEGORY_ID,
        PRIVATE_ROOM_INACTIVE_CATEGORY_ID,
    }


def _non_bot_members(channel: discord.VoiceChannel) -> list[discord.Member]:
    return [member for member in channel.members if not member.bot]


def _managed_private_room_channels(guild: discord.Guild) -> list[discord.VoiceChannel]:
    return [
        channel
        for channel in guild.voice_channels
        if is_managed_private_room(channel)
    ]


def sync_private_room_records_for_guild(guild: discord.Guild) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    summary = {
        "managed_channels": 0,
        "created_records": 0,
        "occupied_records_cleared": 0,
        "empty_records_started": 0,
    }

    for channel in _managed_private_room_channels(guild):
        summary["managed_channels"] += 1
        state = get_private_room_state(guild.id, channel.id)
        non_bot_members = _non_bot_members(channel)
        is_active_room = channel.category_id == PRIVATE_ROOM_ACTIVE_CATEGORY_ID

        if state is None:
            summary["created_records"] += 1
            if non_bot_members or not is_active_room:
                clear_private_room_empty(guild.id, channel.id)
                if non_bot_members:
                    summary["occupied_records_cleared"] += 1
            else:
                mark_private_room_empty(guild.id, channel.id, now)
                summary["empty_records_started"] += 1
            continue

        if state.get("last_empty_at") and (non_bot_members or not is_active_room):
            clear_private_room_empty(guild.id, channel.id)
            if non_bot_members:
                summary["occupied_records_cleared"] += 1

    return summary


def sync_private_room_records(bot) -> dict[str, int]:
    summary = {
        "guild_count": 0,
        "managed_channels": 0,
        "created_records": 0,
        "occupied_records_cleared": 0,
        "empty_records_started": 0,
    }

    for guild in bot.guilds:
        summary["guild_count"] += 1
        guild_summary = sync_private_room_records_for_guild(guild)
        for key, value in guild_summary.items():
            summary[key] += value

    return summary


def _build_manage_channels_sanitized_overwrites(
    channel: discord.abc.GuildChannel,
) -> tuple[bool, dict[discord.abc.Snowflake, discord.PermissionOverwrite], int]:
    updated_overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {}
    changed = False
    changed_targets = 0

    for target, overwrite in channel.overwrites.items():
        values = {name: value for name, value in overwrite if value is not None}
        if values.get("manage_channels") is True:
            values["manage_channels"] = False
            changed = True
            changed_targets += 1
        updated_overwrites[target] = discord.PermissionOverwrite(**values)

    return changed, updated_overwrites, changed_targets


async def _append_channel_to_category_unlocked(
    channel: discord.VoiceChannel,
    target_category: discord.CategoryChannel,
    *,
    reason: str,
):
    await channel.move(category=target_category, end=True, reason=reason)


async def move_channel_to_category_position(
    channel: discord.VoiceChannel,
    target_category: discord.CategoryChannel,
    *,
    reason: str,
):
    guild = channel.guild
    lock = _guild_move_locks.setdefault(guild.id, asyncio.Lock())
    async with lock:
        await _append_channel_to_category_unlocked(
            channel,
            target_category,
            reason=reason,
        )


def _snapshot_category_order(category: discord.CategoryChannel) -> list[int]:
    return [
        channel.id
        for channel in sorted(
            category.voice_channels,
            key=lambda candidate: (candidate.position, candidate.id),
        )
    ]


async def _restore_active_category_order(
    guild: discord.Guild,
    active_category: discord.CategoryChannel,
    snapshot_channel_ids: list[int],
    removed_channel_ids: set[int],
) -> bool:
    current_channels = sorted(
        (
            channel
            for channel in active_category.voice_channels
            if channel.id not in removed_channel_ids
        ),
        key=lambda candidate: (candidate.position, candidate.id),
    )
    channels_by_id = {channel.id: channel for channel in current_channels}

    desired_channels = [
        channels_by_id[channel_id]
        for channel_id in snapshot_channel_ids
        if channel_id in channels_by_id
    ]
    snapshot_ids = set(snapshot_channel_ids)
    desired_channels.extend(
        channel for channel in current_channels if channel.id not in snapshot_ids
    )

    current_ids = [channel.id for channel in current_channels]
    desired_ids = [channel.id for channel in desired_channels]
    if not desired_channels:
        return False
    if current_ids == desired_ids and not removed_channel_ids:
        return False

    payload = [
        {"id": channel.id, "position": position}
        for position, channel in enumerate(desired_channels)
    ]
    await guild._state.http.bulk_channel_update(
        guild.id,
        payload,
        reason="private_room_active_order_restore",
    )
    return True


async def activate_private_room(channel: discord.VoiceChannel, *, reason: str):
    guild = channel.guild
    ensure_private_room_record(guild.id, channel.id)
    clear_private_room_empty(guild.id, channel.id)

    if channel.category_id == PRIVATE_ROOM_ACTIVE_CATEGORY_ID:
        return

    target_category = guild.get_channel(PRIVATE_ROOM_ACTIVE_CATEGORY_ID)
    if isinstance(target_category, discord.CategoryChannel):
        await move_channel_to_category_position(channel, target_category, reason=reason)


async def handle_private_room_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
):
    before_channel = before.channel
    after_channel = after.channel

    if before_channel == after_channel:
        return

    if is_managed_private_room(after_channel):
        await activate_private_room(
            after_channel,
            reason=f"private_room_activated_by_{member.id}",
        )

    if is_managed_private_room(before_channel):
        ensure_private_room_record(before_channel.guild.id, before_channel.id)
        if not _non_bot_members(before_channel):
            mark_private_room_empty(
                before_channel.guild.id,
                before_channel.id,
                datetime.now(timezone.utc),
            )


async def sweep_inactive_private_rooms(bot):
    cutoff = datetime.now(timezone.utc) - timedelta(days=PRIVATE_ROOM_INACTIVITY_DAYS)
    summary = {
        "guild_count": 0,
        "scanned_channels": 0,
        "persisted_channels": 0,
        "created_records": 0,
        "empty_records_started": 0,
        "occupied_records_cleared": 0,
        "archived_channels": 0,
        "restored_active_orders": 0,
        "normalized_channels": 0,
        "normalized_overwrites": 0,
    }

    for guild in bot.guilds:
        summary["guild_count"] += 1
        sync_result = sync_private_room_records_for_guild(guild)
        summary["persisted_channels"] += sync_result["managed_channels"]
        summary["created_records"] += sync_result["created_records"]
        summary["empty_records_started"] += sync_result["empty_records_started"]
        summary["occupied_records_cleared"] += sync_result["occupied_records_cleared"]

        normalize_result = await normalize_private_room_manage_channels(guild)
        summary["normalized_channels"] += normalize_result["corrected_channels"]
        summary["normalized_overwrites"] += normalize_result["corrected_overwrites"]

        active_category = guild.get_channel(PRIVATE_ROOM_ACTIVE_CATEGORY_ID)
        inactive_category = guild.get_channel(PRIVATE_ROOM_INACTIVE_CATEGORY_ID)

        if not isinstance(active_category, discord.CategoryChannel):
            continue
        if not isinstance(inactive_category, discord.CategoryChannel):
            continue

        lock = _guild_move_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            active_order_snapshot = _snapshot_category_order(active_category)
            channels_by_id = {
                channel.id: channel for channel in active_category.voice_channels
            }
            channels_to_archive: list[discord.VoiceChannel] = []

            for channel_id in active_order_snapshot:
                channel = channels_by_id.get(channel_id)
                if channel is None:
                    continue

                summary["scanned_channels"] += 1
                ensure_private_room_record(guild.id, channel.id)

                if _non_bot_members(channel):
                    clear_private_room_empty(guild.id, channel.id)
                    continue

                state = get_private_room_state(guild.id, channel.id)
                last_empty_at = (state or {}).get("last_empty_at") or ""

                if not last_empty_at:
                    mark_private_room_empty(guild.id, channel.id, datetime.now(timezone.utc))
                    continue

                try:
                    last_empty_dt = datetime.fromisoformat(last_empty_at)
                except ValueError:
                    mark_private_room_empty(guild.id, channel.id, datetime.now(timezone.utc))
                    continue

                if last_empty_dt.tzinfo is None:
                    last_empty_dt = last_empty_dt.replace(tzinfo=timezone.utc)

                if last_empty_dt <= cutoff:
                    channels_to_archive.append(channel)

            archived_channel_ids: set[int] = set()
            for channel in channels_to_archive:
                await _append_channel_to_category_unlocked(
                    channel,
                    inactive_category,
                    reason="private_room_auto_archive",
                )
                archived_channel_ids.add(channel.id)
                summary["archived_channels"] += 1
                await asyncio.sleep(0.5)

            restored = await _restore_active_category_order(
                guild,
                active_category,
                active_order_snapshot,
                archived_channel_ids,
            )
            if restored:
                summary["restored_active_orders"] += 1

    return summary


async def scheduled_private_room_sweep_loop(
    bot,
    hour: int = PRIVATE_ROOM_SWEEP_HOUR,
    minute: int = PRIVATE_ROOM_SWEEP_MINUTE,
):
    await bot.wait_until_ready()

    while True:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if target <= now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        try:
            await sweep_inactive_private_rooms(bot)
        except Exception as exc:
            print(f"[PrivateRoom] Sweep failed: {exc}")


def start_private_room_sweep_loop(bot):
    existing_task = getattr(bot, "_private_room_sweep_task", None)
    if existing_task and not existing_task.done():
        return

    bot._private_room_sweep_task = bot.loop.create_task(
        scheduled_private_room_sweep_loop(bot)
    )


async def normalize_private_room_manage_channels(guild: discord.Guild) -> dict[str, int]:
    if not PRIVATE_ROOM_MANAGE_CHANNELS_GUARD_ENABLED:
        return {"corrected_channels": 0, "corrected_overwrites": 0}

    corrected_channels = 0
    corrected_overwrites = 0

    for channel in guild.voice_channels:
        if not is_managed_private_room(channel):
            continue

        changed, overwrites, changed_targets = _build_manage_channels_sanitized_overwrites(channel)
        if not changed:
            continue

        await channel.edit(
            overwrites=overwrites,
            reason="private_room_manage_channels_normalize",
        )
        corrected_channels += 1
        corrected_overwrites += changed_targets
        await asyncio.sleep(0.3)

    return {
        "corrected_channels": corrected_channels,
        "corrected_overwrites": corrected_overwrites,
    }


async def _get_recent_channel_update_actor(
    guild: discord.Guild,
    channel_id: int,
) -> discord.Member | None:
    try:
        async for entry in guild.audit_logs(
            limit=6,
            action=discord.AuditLogAction.channel_update,
        ):
            if not getattr(entry.target, "id", None) == channel_id:
                continue
            created_at = entry.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - created_at > timedelta(seconds=15):
                continue
            if isinstance(entry.user, discord.Member):
                return entry.user
            if entry.user:
                member = guild.get_member(entry.user.id)
                if member:
                    return member
    except discord.Forbidden:
        return None
    except discord.HTTPException:
        return None
    return None


async def rollback_private_room_manage_channels_if_needed(
    before: discord.abc.GuildChannel,
    after: discord.abc.GuildChannel,
):
    if not PRIVATE_ROOM_MANAGE_CHANNELS_GUARD_ENABLED:
        return

    if not is_managed_private_room(after):
        return

    if before.overwrites == after.overwrites:
        return

    changed, overwrites, _changed_targets = _build_manage_channels_sanitized_overwrites(after)
    if not changed:
        return

    actor = await _get_recent_channel_update_actor(after.guild, after.id)
    if actor and actor.guild_permissions.administrator:
        return

    try:
        await after.edit(
            overwrites=overwrites,
            reason="private_room_manage_channels_rollback",
        )
    except discord.HTTPException:
        return
