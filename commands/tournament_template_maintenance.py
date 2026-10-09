import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

TOURNAMENT_TEMPLATE_CATEGORY_ID = 0

LOBBY_CHANNEL_IDS = (
    0,
    0,
)
LOBBY_CONFIG1_NAMES = (
    "A",
    "B",
)
LOBBY_CONFIG2_NAMES = (
    "观赛大厅",
    "观赛广场",
)

EVENT_ROOM_IDS = (
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    
)
EVENT_ROOM_CONFIG1_NAMES = tuple(str(index) for index in range(1, 13))

EVENT_ROLE_IDS = (
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
)


@dataclass(frozen=True)
class TournamentTemplateTarget:
    room_id: int
    role_id: int


TARGETS = tuple(
    TournamentTemplateTarget(room_id=room_id, role_id=role_id)
    for room_id, role_id in zip(EVENT_ROOM_IDS, EVENT_ROLE_IDS, strict=True)
)
TARGET_BY_ROLE_ID = {target.role_id: target for target in TARGETS}


async def purge_channel_messages(channel: discord.abc.GuildChannel) -> int:
    if not hasattr(channel, "history"):
        return 0

    deleted = 0
    recent_batch: list[discord.Message] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    try:
        async for message in channel.history(limit=None, oldest_first=False):
            if message.created_at >= cutoff:
                recent_batch.append(message)
                if len(recent_batch) >= 100:
                    deleted += await _delete_message_batch(channel, recent_batch)
                    recent_batch.clear()
                    await asyncio.sleep(1.0)
            else:
                if recent_batch:
                    deleted += await _delete_message_batch(channel, recent_batch)
                    recent_batch.clear()
                    await asyncio.sleep(1.0)
                try:
                    await message.delete()
                    deleted += 1
                except discord.HTTPException:
                    continue
                await asyncio.sleep(1.2)

        if recent_batch:
            deleted += await _delete_message_batch(channel, recent_batch)
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        return deleted

    return deleted


async def _delete_message_batch(channel: discord.abc.GuildChannel, batch: list[discord.Message]) -> int:
    if not batch:
        return 0

    try:
        if len(batch) == 1:
            await batch[0].delete()
            return 1

        deleted = await channel.delete_messages(batch)
        if deleted is None:
            return len(batch)
        return len(deleted)
    except discord.HTTPException:
        deleted = 0
        for message in batch:
            try:
                await message.delete()
                deleted += 1
            except discord.HTTPException:
                continue
        return deleted


def build_lobby_overwrites(
    guild: discord.Guild,
    *,
    public_visible: bool,
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=public_visible),
    }

    for role_id in EVENT_ROLE_IDS:
        role = guild.get_role(role_id)
        if role is None:
            continue
        overwrites[role] = discord.PermissionOverwrite(move_members=True)

    return overwrites


def build_event_room_overwrites(
    guild: discord.Guild,
    event_role: discord.Role | None,
    *,
    mode: str,
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    if mode == "config1":
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        if event_role is not None:
            overwrites[event_role] = discord.PermissionOverwrite(view_channel=False)
        return overwrites

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            connect=False,
        ),
    }
    if event_role is not None:
        overwrites[event_role] = discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
            move_members=True,
        )
    return overwrites


async def reset_lobby_channel(
    channel: discord.VoiceChannel,
    *,
    public_visible: bool,
    target_name: str,
) -> None:
    overwrites = build_lobby_overwrites(channel.guild, public_visible=public_visible)
    await channel.edit(
        name=target_name,
        overwrites=overwrites,
        reason=f"tournament_template_reset_{'open' if public_visible else 'closed'}",
    )


async def reset_event_room(
    channel: discord.VoiceChannel,
    event_role: discord.Role | None,
    *,
    mode: str,
    target_name: str | None = None,
) -> None:
    overwrites = build_event_room_overwrites(channel.guild, event_role, mode=mode)
    edit_kwargs = {
        "overwrites": overwrites,
        "reason": f"tournament_template_reset_{mode}",
    }
    if target_name is not None:
        edit_kwargs["name"] = target_name
    await channel.edit(**edit_kwargs)


async def clear_event_role_members(guild: discord.Guild) -> tuple[int, int]:
    affected_members: set[int] = set()
    removed_roles = 0

    for role_id in EVENT_ROLE_IDS:
        role = guild.get_role(role_id)
        if role is None:
            continue

        for member in list(role.members):
            try:
                await member.remove_roles(role, reason="tournament_template_reset_config1")
                affected_members.add(member.id)
                removed_roles += 1
                await asyncio.sleep(0.1)
            except discord.HTTPException:
                continue

    return len(affected_members), removed_roles


async def clear_single_event_role_members(guild: discord.Guild, role_id: int) -> tuple[int, int]:
    role = guild.get_role(role_id)
    if role is None:
        return 0, 0

    affected_members: set[int] = set()
    removed_roles = 0

    for member in list(role.members):
        try:
            await member.remove_roles(role, reason="tournament_team_eliminated")
            affected_members.add(member.id)
            removed_roles += 1
            await asyncio.sleep(0.1)
        except discord.HTTPException:
            continue

    return len(affected_members), removed_roles


async def apply_tournament_template(guild: discord.Guild, *, mode: str) -> dict[str, int]:
    category = guild.get_channel(TOURNAMENT_TEMPLATE_CATEGORY_ID)
    if not isinstance(category, discord.CategoryChannel):
        raise RuntimeError("赛事模板类别不存在")

    deleted_messages = 0
    reset_channels = 0

    lobby_names = LOBBY_CONFIG2_NAMES if mode == "config2" else LOBBY_CONFIG1_NAMES
    for channel_id, target_name in zip(LOBBY_CHANNEL_IDS, lobby_names, strict=True):
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.VoiceChannel):
            deleted_messages += await purge_channel_messages(channel)
            await reset_lobby_channel(
                channel,
                public_visible=(mode == "config2"),
                target_name=target_name,
            )
            reset_channels += 1

    for index, target in enumerate(TARGETS):
        channel = guild.get_channel(target.room_id)
        role = guild.get_role(target.role_id)
        if isinstance(channel, discord.VoiceChannel):
            deleted_messages += await purge_channel_messages(channel)
            await reset_event_room(
                channel,
                role,
                mode=mode,
                target_name=EVENT_ROOM_CONFIG1_NAMES[index] if mode == "config1" else None,
            )
            reset_channels += 1

    cleared_members = 0
    removed_roles = 0
    if mode == "config1":
        cleared_members, removed_roles = await clear_event_role_members(guild)

    return {
        "reset_channels": reset_channels,
        "deleted_messages": deleted_messages,
        "cleared_members": cleared_members,
        "removed_roles": removed_roles,
    }


async def reset_single_event_team(guild: discord.Guild, event_role: discord.Role) -> dict[str, int]:
    target = TARGET_BY_ROLE_ID.get(event_role.id)
    if target is None:
        raise RuntimeError("这个身份组不在赛事模板映射里")

    channel = guild.get_channel(target.room_id)
    if not isinstance(channel, discord.VoiceChannel):
        raise RuntimeError("对应赛事房间不存在")

    target_index = EVENT_ROLE_IDS.index(event_role.id)

    deleted_messages = await purge_channel_messages(channel)
    await reset_event_room(
        channel,
        event_role,
        mode="config1",
        target_name=EVENT_ROOM_CONFIG1_NAMES[target_index],
    )
    cleared_members, removed_roles = await clear_single_event_role_members(guild, event_role.id)

    return {
        "room_id": channel.id,
        "room_name": channel.name,
        "deleted_messages": deleted_messages,
        "cleared_members": cleared_members,
        "removed_roles": removed_roles,
    }


def setup(bot):
    @bot.command(name="赛事模板", aliases=["tournamenttemplate"])
    @commands.has_permissions(administrator=True)
    async def tournament_template(ctx: commands.Context, mode: str):
        normalized = mode.strip().lower()
        if normalized not in {"配置1", "配置2", "config1", "config2"}:
            await ctx.send("用法：`&赛事模板 配置1` 或 `&赛事模板 配置2`")
            return

        target_mode = "config1" if normalized in {"配置1", "config1"} else "config2"

        async with ctx.typing():
            try:
                result = await apply_tournament_template(ctx.guild, mode=target_mode)
            except RuntimeError as exc:
                await ctx.send(f"执行失败：{exc}")
                return

        embed = discord.Embed(
            title="赛事模板已复原",
            color=discord.Color.orange() if target_mode == "config1" else discord.Color.green(),
            description=(
                f"已应用：{target_mode}\n"
                f"已重置频道：{result['reset_channels']}\n"
                f"已清空消息：{result['deleted_messages']}\n"
                f"已清空赛事组成员：{result['cleared_members']}\n"
                f"已移除赛事组持有次数：{result['removed_roles']}"
            ),
        )
        await ctx.send(embed=embed)

    @bot.command(name="kill")
    @commands.has_permissions(administrator=True)
    async def kill_team(ctx: commands.Context, role: discord.Role):
        if role.id not in TARGET_BY_ROLE_ID:
            await ctx.send("这个身份组不在赛事模板映射里。")
            return

        async with ctx.typing():
            try:
                result = await reset_single_event_team(ctx.guild, role)
            except RuntimeError as exc:
                await ctx.send(f"执行失败：{exc}")
                return

        embed = discord.Embed(
            title="赛事队伍已回收",
            color=discord.Color.red(),
            description=(
                f"目标赛事组：{role.mention}\n"
                f"对应房间：<#{result['room_id']}>\n"
                f"已清空消息：{result['deleted_messages']}\n"
                f"已清空赛事组成员：{result['cleared_members']}\n"
                f"已移除赛事组持有次数：{result['removed_roles']}"
            ),
        )
        await ctx.send(embed=embed)
