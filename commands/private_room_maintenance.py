from datetime import datetime, timezone

import discord
from discord.ext import commands

from config.constants import (
    NEWBEEMANAGER_ROLE_ID,
    PRIVATE_ROOM_ACTIVE_CATEGORY_ID,
    PRIVATE_ROOM_INACTIVE_CATEGORY_ID,
    PRIVATE_ROOM_INACTIVITY_DAYS,
)
from database.private_room_state import get_private_room_state
from services.private_room_manager import (
    is_managed_private_room,
    sync_private_room_records_for_guild,
    sweep_inactive_private_rooms,
)
from services.role_utils import has_role_by_id


def _format_days_since_empty(last_empty_at: str) -> str:
    if not last_empty_at:
        return "未开始计时"

    try:
        last_empty_dt = datetime.fromisoformat(last_empty_at)
    except ValueError:
        return "时间戳异常"

    if last_empty_dt.tzinfo is None:
        last_empty_dt = last_empty_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    days = max(0, (now - last_empty_dt).days)
    return f"{days} 天"


def _parse_last_empty_at(last_empty_at: str) -> datetime | None:
    if not last_empty_at:
        return None

    try:
        last_empty_dt = datetime.fromisoformat(last_empty_at)
    except ValueError:
        return None

    if last_empty_dt.tzinfo is None:
        last_empty_dt = last_empty_dt.replace(tzinfo=timezone.utc)
    return last_empty_dt


def _format_last_used_time(last_empty_dt: datetime) -> str:
    unix_ts = int(last_empty_dt.timestamp())
    return f"<t:{unix_ts}:F>（<t:{unix_ts}:R>）"


def _build_channel_lines(
    channels: list[discord.VoiceChannel],
    guild: discord.Guild,
) -> tuple[list[str], dict, list[str], str | None]:
    lines: list[str] = []
    nearing_due_lines: list[str] = []
    closest_downgrade: tuple[int, str] | None = None
    summary = {
        "active_count": 0,
        "inactive_count": 0,
        "occupied_count": 0,
        "empty_count": 0,
        "nearing_due_count": 0,
        "missing_state_count": 0,
    }

    now = datetime.now(timezone.utc)

    for channel in channels:
        if channel.category_id == PRIVATE_ROOM_ACTIVE_CATEGORY_ID:
            summary["active_count"] += 1
            category_label = "活跃"
        else:
            summary["inactive_count"] += 1
            category_label = "保留"

        non_bot_members = [member for member in channel.members if not member.bot]
        if non_bot_members:
            summary["occupied_count"] += 1
            usage_label = f"使用中（{len(non_bot_members)}人）"
        else:
            summary["empty_count"] += 1
            usage_label = "空房"

        state = get_private_room_state(guild.id, channel.id)
        last_empty_at = (state or {}).get("last_empty_at") or ""
        if state is None:
            summary["missing_state_count"] += 1

        due_label = ""
        if last_empty_at:
            last_empty_dt = _parse_last_empty_at(last_empty_at)
            if last_empty_dt is not None:
                empty_days = (now - last_empty_dt).days
                remaining_days = PRIVATE_ROOM_INACTIVITY_DAYS - empty_days
                if channel.category_id == PRIVATE_ROOM_ACTIVE_CATEGORY_ID and remaining_days >= 0:
                    closest_line = (
                        f"{channel.name} ({channel.id})\n"
                        f"最后使用：{_format_last_used_time(last_empty_dt)}\n"
                        f"空置：{empty_days} 天｜距下调：{remaining_days} 天"
                    )
                    if closest_downgrade is None or remaining_days < closest_downgrade[0]:
                        closest_downgrade = (remaining_days, closest_line)

                if 0 <= remaining_days <= 7:
                    summary["nearing_due_count"] += 1
                    due_label = f" | 距迁移 {remaining_days} 天"
                    nearing_due_lines.append(
                        f"{channel.name} ({channel.id}) | 类别:{category_label} | 空置:{empty_days} 天 | 距迁移:{remaining_days} 天"
                    )
            else:
                due_label = " | 时间戳异常"

        lines.append(
            " | ".join(
                [
                    f"{channel.name} ({channel.id})",
                    f"类别:{category_label}",
                    f"状态:{usage_label}",
                    f"空置计时:{_format_days_since_empty(last_empty_at)}{due_label}",
                ]
            )
        )

    return lines, summary, nearing_due_lines, closest_downgrade[1] if closest_downgrade else None


def setup(bot):
    @bot.command(name="私房巡检", aliases=["roomcheck"])
    @has_role_by_id(NEWBEEMANAGER_ROLE_ID)
    async def private_room_check(ctx: commands.Context):
        guild = ctx.guild

        managed_channels = [
            channel
            for channel in guild.voice_channels
            if is_managed_private_room(channel)
        ]

        managed_channels.sort(
            key=lambda channel: (
                0 if channel.category_id == PRIVATE_ROOM_ACTIVE_CATEGORY_ID else 1,
                channel.position,
            )
        )

        sync_result = sync_private_room_records_for_guild(guild)
        _lines, summary, nearing_due_lines, closest_downgrade_line = _build_channel_lines(managed_channels, guild)

        embed = discord.Embed(
            title="私房巡检",
            color=discord.Color.blue(),
            description=(
                f"活跃私房：{summary['active_count']}\n"
                f"保留私房：{summary['inactive_count']}\n"
                f"当前使用中：{summary['occupied_count']}\n"
                f"当前空房：{summary['empty_count']}\n"
                f"临近 {PRIVATE_ROOM_INACTIVITY_DAYS} 天迁移线（7天内）：{summary['nearing_due_count']}\n"
                f"尚未建档：{summary['missing_state_count']}\n"
                f"本次对齐：新增 {sync_result['created_records']} 条，活跃空房开始计时 {sync_result['empty_records_started']} 间"
            ),
        )

        embed.add_field(
            name="最接近下调",
            value=closest_downgrade_line or "当前没有已开始计时的活跃空房。",
            inline=False,
        )

        preview_lines = nearing_due_lines[:10]
        if preview_lines:
            embed.add_field(
                name="临近迁移线",
                value="\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(preview_lines))[:1024],
                inline=False,
            )
        else:
            embed.add_field(
                name="临近迁移线",
                value="当前没有 7 天内将触发自动迁移的私房。",
                inline=False,
            )

        await ctx.send(embed=embed)

    @bot.command(name="私房测试", aliases=["roomtest"])
    @has_role_by_id(NEWBEEMANAGER_ROLE_ID)
    async def private_room_test(ctx: commands.Context):
        result = await sweep_inactive_private_rooms(ctx.bot)

        embed = discord.Embed(
            title="私房测试",
            color=discord.Color.gold(),
            description=(
                "已手动执行一次每日私房清扫任务。\n"
                f"扫描服务器数：{result['guild_count']}\n"
                f"持久化私房：{result['persisted_channels']}\n"
                f"新增建档：{result['created_records']}\n"
                f"扫描活跃私房：{result['scanned_channels']}\n"
                f"自动归档私房：{result['archived_channels']}\n"
                f"修正权限频道：{result['normalized_channels']}\n"
                f"修正权限条目：{result['normalized_overwrites']}"
            ),
        )

        await ctx.send(embed=embed)
