import asyncio
import io
from dataclasses import dataclass

import discord

from config.constants import NEWBEEMANAGER_ROLE_ID
from config.level_roles import LEVEL_ROLE_MAP
from database.dao_user import get_all_users
from services.role_utils import check_level_change, has_role_by_id
from services.xp_tracker import get_level_from_xp


@dataclass
class RoleIssue:
    user_id: str
    display_name: str | None
    issue_type: str
    expected_role_id: int | None
    expected_role_name: str | None
    actual_level_roles: list[discord.Role]
    total_level: int
    last_active_date: str


def compute_expected_role(user):
    text_level = get_level_from_xp("text", user.text_xp)
    voice_level = get_level_from_xp("voice", user.voice_xp)
    stream_level = get_level_from_xp("stream", user.stream_xp)
    total_level = text_level + voice_level + stream_level

    expected_role_id = None
    expected_role_name = None
    for level, name, role_id in sorted(LEVEL_ROLE_MAP, reverse=True):
        if total_level >= level and role_id:
            expected_role_id = role_id
            expected_role_name = name
            break

    return {
        "total_level": total_level,
        "expected_role_id": expected_role_id,
        "expected_role_name": expected_role_name,
        "last_active_date": user.last_active_date,
    }


def classify_issue(expected_role_id, actual_level_roles):
    actual_role_ids = {role.id for role in actual_level_roles}
    if expected_role_id is None:
        return "unexpected_level_role" if actual_level_roles else None
    if not actual_level_roles:
        return "missing_expected_role"
    if actual_role_ids == {expected_role_id}:
        return None
    if len(actual_level_roles) == 1:
        return "wrong_single_level_role"
    return "multiple_or_mixed_level_roles"


async def audit_level_roles_from_db(guild: discord.Guild):
    if not guild.chunked:
        await guild.chunk(cache=True)

    level_role_ids = {role_id for _, _, role_id in LEVEL_ROLE_MAP if role_id}
    issues: list[RoleIssue] = []

    for user in get_all_users():
        expected = compute_expected_role(user)
        member = guild.get_member(int(user.user_id))
        if member is None:
            issues.append(
                RoleIssue(
                    user_id=str(user.user_id),
                    display_name=None,
                    issue_type="user_not_in_guild",
                    expected_role_id=expected["expected_role_id"],
                    expected_role_name=expected["expected_role_name"],
                    actual_level_roles=[],
                    total_level=expected["total_level"],
                    last_active_date=expected["last_active_date"],
                )
            )
            continue

        actual_level_roles = [role for role in member.roles if role.id in level_role_ids]
        issue_type = classify_issue(expected["expected_role_id"], actual_level_roles)
        if issue_type is None:
            continue

        issues.append(
            RoleIssue(
                user_id=str(user.user_id),
                display_name=member.display_name,
                issue_type=issue_type,
                expected_role_id=expected["expected_role_id"],
                expected_role_name=expected["expected_role_name"],
                actual_level_roles=actual_level_roles,
                total_level=expected["total_level"],
                last_active_date=expected["last_active_date"],
            )
        )

    summary = {
        "user_not_in_guild": sum(1 for item in issues if item.issue_type == "user_not_in_guild"),
        "missing_expected_role": sum(1 for item in issues if item.issue_type == "missing_expected_role"),
        "wrong_single_level_role": sum(1 for item in issues if item.issue_type == "wrong_single_level_role"),
        "multiple_or_mixed_level_roles": sum(1 for item in issues if item.issue_type == "multiple_or_mixed_level_roles"),
        "unexpected_level_role": sum(1 for item in issues if item.issue_type == "unexpected_level_role"),
    }
    return issues, summary


def build_summary_text(summary: dict) -> str:
    actionable = (
        summary["missing_expected_role"]
        + summary["wrong_single_level_role"]
        + summary["multiple_or_mixed_level_roles"]
        + summary["unexpected_level_role"]
    )
    return (
        f"巡检完成。\n"
        f"可操作异常：{actionable}\n"
        f"缺失应有等级组：{summary['missing_expected_role']}\n"
        f"错挂单个等级组：{summary['wrong_single_level_role']}\n"
        f"多挂或混挂等级组：{summary['multiple_or_mixed_level_roles']}\n"
        f"不应有却持有等级组：{summary['unexpected_level_role']}\n"
        f"数据库在服外用户：{summary['user_not_in_guild']}"
    )


def build_missing_report(issues: list[RoleIssue]) -> discord.File:
    missing = [issue for issue in issues if issue.issue_type == "missing_expected_role"]
    lines = [
        "身份组缺失名单",
        f"总人数：{len(missing)}",
        "",
    ]

    for idx, issue in enumerate(missing, start=1):
        expected = f"{issue.expected_role_name} ({issue.expected_role_id})" if issue.expected_role_id else "无"
        lines.extend(
            [
                f"{idx}. <@{issue.user_id}>",
                f"   昵称：{issue.display_name or '未知'}",
                f"   应有身份组：{expected}",
                f"   总等级：{issue.total_level}",
                f"   最后活跃日期：{issue.last_active_date or '无'}",
                "",
            ]
        )

    fp = io.BytesIO("\n".join(lines).encode("utf-8"))
    return discord.File(fp=fp, filename="身份组缺失名单.txt")


class LevelRoleMaintenanceView(discord.ui.View):
    def __init__(self, invoker_id: int):
        super().__init__(timeout=900)
        self.invoker_id = invoker_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("只有发起巡检的人可以操作这些按钮。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="输出身份组缺失名单", style=discord.ButtonStyle.secondary)
    async def export_missing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        issues, summary = await audit_level_roles_from_db(interaction.guild)
        missing_count = summary["missing_expected_role"]
        if missing_count == 0:
            await interaction.followup.send("当前没有缺失应有等级组的成员。", ephemeral=True)
            return

        await interaction.followup.send(
            content=f"已导出缺失名单，共 {missing_count} 人。",
            file=build_missing_report(issues),
            ephemeral=True,
        )

    @discord.ui.button(label="将身份组对正", style=discord.ButtonStyle.danger)
    async def repair_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        issues, _summary = await audit_level_roles_from_db(interaction.guild)
        actionable = [
            issue for issue in issues
            if issue.issue_type in {
                "missing_expected_role",
                "wrong_single_level_role",
                "multiple_or_mixed_level_roles",
                "unexpected_level_role",
            }
        ]

        fixed = 0
        skipped = 0
        for issue in actionable:
            member = interaction.guild.get_member(int(issue.user_id))
            if member is None:
                skipped += 1
                continue
            await check_level_change(member)
            fixed += 1
            await asyncio.sleep(0.2)

        _issues_after, summary_after = await audit_level_roles_from_db(interaction.guild)
        remaining = (
            summary_after["missing_expected_role"]
            + summary_after["wrong_single_level_role"]
            + summary_after["multiple_or_mixed_level_roles"]
            + summary_after["unexpected_level_role"]
        )

        await interaction.followup.send(
            (
                f"身份组对正已执行。\n"
                f"本次处理：{fixed}\n"
                f"跳过：{skipped}\n"
                f"剩余可操作异常：{remaining}"
            ),
            ephemeral=True,
        )


def setup(bot):
    @bot.command(name="等级组巡检", aliases=["rolesync"])
    @has_role_by_id(NEWBEEMANAGER_ROLE_ID)
    async def level_role_maintenance(ctx):
        _issues, summary = await audit_level_roles_from_db(ctx.guild)
        actionable = (
            summary["missing_expected_role"]
            + summary["wrong_single_level_role"]
            + summary["multiple_or_mixed_level_roles"]
            + summary["unexpected_level_role"]
        )

        embed = discord.Embed(
            title="等级身份组巡检",
            description=build_summary_text(summary),
            color=discord.Color.orange() if actionable else discord.Color.green(),
        )
        embed.add_field(
            name="操作说明",
            value="如果存在缺漏，可使用下方按钮导出缺失名单，或直接执行身份组对正。",
            inline=False,
        )
        await ctx.reply(
            embed=embed,
            view=LevelRoleMaintenanceView(ctx.author.id),
            mention_author=True,
        )
