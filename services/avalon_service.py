import asyncio
import random
from datetime import datetime, timezone
from pathlib import Path

import discord

from database import avalon_db
from services import avalon_rules as rules


CARD_DIR = Path(__file__).resolve().parents[1] / "assets" / "avalon" / "cards"
ROLE_GALLERY_URL = "https://avalon.local/role-cards"
ROLE_ASSET_KEYS = {
    rules.MERLIN: "merlin",
    rules.PERCIVAL: "percival",
    rules.LOYAL_SERVANT: "loyal_servant",
    rules.ASSASSIN: "assassin",
    rules.MORGANA: "morgana",
    rules.MORDRED: "mordred",
    rules.OBERON: "oberon",
    rules.MINION: "minion",
}
ROLE_FRONT_VARIANTS = {
    rules.LOYAL_SERVANT: (
        "loyal_servant_1",
        "loyal_servant_2",
        "loyal_servant_3",
    ),
    rules.MINION: (
        "minion_1",
        "minion_2",
        "minion_3",
    ),
}


PHASE_NAMES = {
    "LOBBY": "等待玩家加入",
    "ROLE_CONFIRMATION": "确认秘密身份",
    "TEAM_PROPOSAL": "队长提名任务队伍",
    "TEAM_VOTE": "全员秘密投票",
    "TEAM_VOTE_RESULT": "公布组队投票",
    "QUEST_SUBMISSION": "任务成员秘密行动",
    "QUEST_RESULT": "公布任务结果",
    "ASSASSINATION": "刺杀梅林",
    "FINISHED": "游戏结束",
    "CANCELLED": "游戏已取消",
}

ROLE_DESCRIPTIONS = {
    rules.MERLIN: "你知道除莫德雷德以外的邪恶玩家，但必须隐藏自己，避免最终被刺客识破。",
    rules.PERCIVAL: "你能看到梅林候选人；若莫甘娜在场，你无法分辨两者真假。",
    rules.LOYAL_SERVANT: "你没有开局情报，只能依靠组队、投票、任务结果与发言推理。",
    rules.ASSASSIN: "你属于邪恶阵营。好人完成三个任务后，由你选择刺杀目标。",
    rules.MORGANA: "你属于邪恶阵营，并会在派西维尔眼中伪装成梅林。",
    rules.MORDRED: "你属于邪恶阵营，梅林无法感知到你。",
    rules.OBERON: "你属于邪恶阵营，但你与其他邪恶玩家互不相认。梅林仍能感知到你。",
    rules.MINION: "你属于邪恶阵营，可以在任务中选择成功或失败。",
}


ROLE_DUTIES = {
    rules.MERLIN: "谨慎引导好人完成三个任务，同时隐藏自己，避免最终被刺客认出。任务中你只能提交成功。",
    rules.PERCIVAL: "辨别并保护真正的梅林，帮助好人排除可疑队伍。任务中你只能提交成功。",
    rules.LOYAL_SERVANT: "通过组队、投票和任务结果找出坏人，协助完成三个任务。任务中你只能提交成功。",
    rules.ASSASSIN: "混入任务并误导好人；若好人先完成三个任务，找出并刺杀梅林。任务中可提交成功或失败。",
    rules.MORGANA: "伪装成梅林误导派西维尔，并协助坏人破坏三个任务。任务中可提交成功或失败。",
    rules.MORDRED: "利用梅林看不到你的优势潜伏并破坏任务。任务中可提交成功或失败。",
    rules.OBERON: "独立判断其他坏人的行动，在不暴露自己的情况下协助破坏任务。任务中可提交成功或失败。",
    rules.MINION: "隐藏邪恶身份，误导组队和投票，并协助破坏三个任务。任务中可提交成功或失败。",
}

INACTIVITY_TIMEOUT_SECONDS = 60 * 60
RESET_CONFIRM_SECONDS = 60
CLEANUP_INTERVAL_SECONDS = 5 * 60


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def is_game_inactive(state: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    last_active = _parse_iso(state.get("last_interaction_at") or state.get("created_at"))
    if last_active is None:
        return False
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)
    return (now - last_active).total_seconds() >= INACTIVITY_TIMEOUT_SECONDS


def _touch(state: dict):
    state["last_interaction_at"] = _now_iso()


def _mention(user_id: str) -> str:
    return f"<@{user_id}>"


def _player_ids(state: dict) -> list[str]:
    return [str(player["id"]) for player in state["players"]]


def _leader_id(state: dict) -> str | None:
    players = _player_ids(state)
    if not players or state.get("leader_index") is None:
        return None
    return players[int(state["leader_index"]) % len(players)]


def _player_display(state: dict, user_id: str) -> str:
    user_id = str(user_id)
    for player in state.get("players", []):
        if str(player["id"]) == user_id:
            if player.get("simulated"):
                return str(player["name"])
            return _mention(user_id)
    return _mention(user_id)


def _seat_number(state: dict, user_id: str) -> int | None:
    user_id = str(user_id)
    for index, player in enumerate(state.get("players", []), start=1):
        if str(player["id"]) == user_id:
            return index
    return None


def _player_line(state: dict, user_id: str) -> str:
    seat = _seat_number(state, user_id)
    prefix = f"{seat}. " if seat is not None else ""
    return f"{prefix}{_player_display(state, user_id)}"


def _player_list_text(state: dict, user_ids: list[str]) -> str:
    lines = [_player_line(state, user_id) for user_id in user_ids]
    return "\n".join(lines) if lines else "尚未选择"


def _quest_track(state: dict) -> str:
    symbols = ["🔵" if value else "🔴" for value in state.get("quest_results", [])]
    symbols.extend(["⚪"] * (5 - len(symbols)))
    return " ".join(symbols)


def _vote_track(state: dict) -> str:
    rejected = int(state.get("reject_count", 0))
    return " ".join(["🔴"] * rejected + ["⚪"] * (5 - rejected)) + f"  {rejected}/5"


def _seat_text(state: dict) -> str:
    return "\n".join(
        _player_line(state, str(player["id"]))
        for player in state.get("players", [])
    ) or "等待玩家"


SPECIAL_ROLES = (
    rules.MERLIN,
    rules.PERCIVAL,
    rules.ASSASSIN,
    rules.MORGANA,
    rules.MORDRED,
    rules.OBERON,
)


def _role_configuration_text(state: dict) -> str:
    roles = list(state.get("roles", {}).values())
    assigned = set(roles)
    names = [rules.ROLE_NAMES[role] for role in SPECIAL_ROLES if role in assigned]
    special_roles = " · ".join(names) if names else "无特殊身份"
    evil_count = sum(rules.side_for_role(role) == rules.EVIL for role in roles)
    return f"{special_roles}\n邪恶阵营：{evil_count} 人"


def _knowledge_text(state: dict, user_id: str) -> str:
    knowledge = rules.knowledge_for_player(user_id, state["roles"])
    visible = set(str(value) for value in knowledge["visible_players"])
    ordered = [
        str(player["id"])
        for player in state.get("players", [])
        if str(player["id"]) in visible
    ]
    ordered.extend(sorted(visible.difference(ordered)))
    return _player_list_text(state, ordered) if ordered else "没有人"


def action_specs_for_state(state: dict) -> list[tuple[str, str, discord.ButtonStyle, int]]:
    status = state["status"]
    specs: list[tuple[str, str, discord.ButtonStyle, int]] = []

    if status in avalon_db.ACTIVE_STATUSES:
        if status != "LOBBY":
            specs.append(("view_role", "查看身份", discord.ButtonStyle.secondary, 0))
        specs.append(("reset", "清空 / 重置", discord.ButtonStyle.danger, 0))

    if status == "ASSASSINATION":
        specs.append(("assassinate", "刺杀梅林", discord.ButtonStyle.danger, 0))
    elif status == "LOBBY":
        specs.extend([
            ("join", "加入游戏", discord.ButtonStyle.success, 1),
            ("leave", "退出游戏", discord.ButtonStyle.secondary, 1),
            ("start", "开始游戏", discord.ButtonStyle.primary, 1),
        ])
    elif status == "ROLE_CONFIRMATION":
        specs.append(("confirm_role", "确认身份", discord.ButtonStyle.success, 1))
    elif status == "TEAM_PROPOSAL":
        specs.append(("team_select", "选择队伍", discord.ButtonStyle.primary, 1))
    elif status == "TEAM_VOTE":
        specs.extend([
            ("vote_approve", "赞成", discord.ButtonStyle.success, 1),
            ("vote_reject", "反对", discord.ButtonStyle.danger, 1),
        ])
    elif status in {"TEAM_VOTE_RESULT", "QUEST_RESULT"}:
        specs.append(("continue", "继续", discord.ButtonStyle.primary, 1))
    elif status == "QUEST_SUBMISSION":
        specs.extend([
            ("quest_success", "任务成功", discord.ButtonStyle.success, 1),
            ("quest_fail", "任务失败", discord.ButtonStyle.danger, 1),
        ])
    return specs


class AvalonActionButton(discord.ui.Button):
    def __init__(self, service, action: str, label: str, style: discord.ButtonStyle, row: int = 0):
        super().__init__(
            label=label,
            style=style,
            custom_id=f"avalon:{action}",
            row=row,
        )
        self.service = service
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        await self.service.handle_action(interaction, self.action)


class AvalonGameView(discord.ui.View):
    def __init__(self, service, state: dict):
        super().__init__(timeout=None)
        self.service = service
        for action, label, style, row in action_specs_for_state(state):
            if action == "team_select":
                self.add_item(AvalonTeamSelect(service, state["id"], state, row=row))
            else:
                self.add_item(AvalonActionButton(service, action, label, style, row=row))


class AvalonTeamSelect(discord.ui.Select):
    def __init__(self, service, game_id: int, state: dict, row: int = 1):
        team_size = rules.quest_team_size(len(state["players"]), int(state["quest_index"]))
        options = [
            discord.SelectOption(label=player["name"][:100], value=str(player["id"]))
            for player in state["players"]
        ]
        super().__init__(
            placeholder=f"选择 {team_size} 名任务成员",
            min_values=team_size,
            max_values=team_size,
            options=options,
            custom_id="avalon:team_select",
            row=row,
        )
        self.service = service
        self.game_id = game_id

    async def callback(self, interaction: discord.Interaction):
        await self.service.submit_team(interaction, self.game_id, list(self.values))


class AvalonAssassinationSelect(discord.ui.Select):
    def __init__(self, service, game_id: int, state: dict):
        roles = state["roles"]
        options = [
            discord.SelectOption(label=player["name"][:100], value=str(player["id"]))
            for player in state["players"]
            if rules.side_for_role(roles[str(player["id"])]) == rules.GOOD
        ]
        super().__init__(
            placeholder="刺客选择一名好人作为刺杀目标",
            options=options,
            custom_id="avalon:assassination_select",
        )
        self.service = service
        self.game_id = game_id

    async def callback(self, interaction: discord.Interaction):
        await self.service.submit_assassination(interaction, self.game_id, self.values[0])


class AvalonService:
    def __init__(self, bot):
        self.bot = bot
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, game_id: int) -> asyncio.Lock:
        return self._locks.setdefault(int(game_id), asyncio.Lock())

    async def create_lobby(self, guild: discord.Guild, channel, owner: discord.Member):
        existing = await asyncio.to_thread(avalon_db.get_active_game_for_channel, channel.id)
        if existing:
            return False, "本频道已经有一局未结束的阿瓦隆。"

        state = {
            "guild_id": str(guild.id),
            "channel_id": str(channel.id),
            "message_id": "",
            "owner_id": str(owner.id),
            "status": "LOBBY",
            "players": [],
            "settings": {},
            "roles": {},
            "role_viewed": [],
            "role_confirmed": [],
            "leader_index": None,
            "quest_index": 0,
            "reject_count": 0,
            "quest_results": [],
            "proposed_team": [],
            "votes": {},
            "quest_submissions": {},
            "vote_result": None,
            "quest_result": None,
            "winner": None,
            "end_reason": None,
            "created_at": _now_iso(),
            "last_interaction_at": _now_iso(),
            "reset_confirmations": {},
        }
        state = await asyncio.to_thread(avalon_db.create_game, state)
        message = await channel.send(embed=self.build_embed(state), view=AvalonGameView(self, state))
        state["message_id"] = str(message.id)
        await asyncio.to_thread(avalon_db.save_game, state)
        return True, f"阿瓦隆大厅已创建（游戏 #{state['id']}）。"

    async def restore_views(self):
        games = await asyncio.to_thread(avalon_db.list_active_games)
        for state in games:
            try:
                self.bot.add_view(
                    AvalonGameView(self, state),
                    message_id=int(state["message_id"]),
                )
            except (TypeError, ValueError):
                continue
        return len(games)

    def build_embed(self, state: dict) -> discord.Embed:
        status = state["status"]
        color = {
            "LOBBY": 0x5865F2,
            "ROLE_CONFIRMATION": 0x8E44AD,
            "TEAM_PROPOSAL": 0x3498DB,
            "TEAM_VOTE": 0xF1C40F,
            "TEAM_VOTE_RESULT": 0xF39C12,
            "QUEST_SUBMISSION": 0x9B59B6,
            "QUEST_RESULT": 0x2ECC71,
            "ASSASSINATION": 0xE74C3C,
            "FINISHED": 0x95A5A6,
            "CANCELLED": 0x7F8C8D,
        }.get(status, 0x5865F2)
        embed = discord.Embed(title="⚔️ 阿瓦隆", color=color)

        if status == "LOBBY":
            embed.description = "等待玩家入席。"
            embed.add_field(name=f"玩家 · {len(state['players'])}/10", value=_seat_text(state), inline=False)
            embed.add_field(name="房主", value=_player_display(state, state["owner_id"]), inline=False)
        elif status == "ROLE_CONFIRMATION":
            embed.description = "查看你的身份，然后准备出发。"
            embed.add_field(name="座次", value=_seat_text(state), inline=False)
            embed.add_field(name="本局角色", value=_role_configuration_text(state), inline=False)
            embed.add_field(name="任务", value=_quest_track(state), inline=False)
            embed.add_field(name="队长", value=_player_line(state, _leader_id(state)), inline=True)
            embed.add_field(name="否决", value=_vote_track(state), inline=False)
            embed.add_field(name="准备", value=f"{len(state['role_confirmed'])}/{len(state['players'])}", inline=True)
        elif status not in {"FINISHED", "CANCELLED"}:
            quest_number = int(state["quest_index"]) + 1
            embed.add_field(name="座次", value=_seat_text(state), inline=False)
            embed.add_field(name="本局角色", value=_role_configuration_text(state), inline=False)
            embed.add_field(name="任务", value=_quest_track(state), inline=False)
            embed.add_field(name="队长", value=_player_line(state, _leader_id(state)), inline=True)
            embed.add_field(name="否决", value=_vote_track(state), inline=False)
            embed.add_field(name="队伍", value=_player_list_text(state, list(state.get("proposed_team", []))), inline=False)

            if status == "TEAM_PROPOSAL":
                size = rules.quest_team_size(len(state["players"]), int(state["quest_index"]))
                threshold = rules.fails_required(len(state["players"]), int(state["quest_index"]))
                embed.description = f"**第 {quest_number} 次任务**\n队长选择 {size} 人出发。"
                if threshold == 2:
                    embed.description += "\n本轮需要两张失败牌。"
            elif status == "TEAM_VOTE":
                embed.description = f"**第 {quest_number} 次任务**\n为这支队伍投票。"
                embed.add_field(name="已投票", value=f"{len(state['votes'])}/{len(state['players'])}", inline=True)
            elif status == "TEAM_VOTE_RESULT":
                result = state["vote_result"]
                embed.description = "队伍通过。" if result["passed"] else "队伍被否决。"
                lines = [
                    f"{_player_line(state, uid)} · {'赞成' if result['votes'][uid] == 'APPROVE' else '反对'}"
                    for uid in _player_ids(state)
                ]
                embed.add_field(name="投票", value="\n".join(lines), inline=False)
            elif status == "QUEST_SUBMISSION":
                embed.description = f"**第 {quest_number} 次任务**\n任务成员选择行动。"
                embed.add_field(name="已行动", value=f"{len(state['quest_submissions'])}/{len(state['proposed_team'])}", inline=True)
            elif status == "QUEST_RESULT":
                result = state["quest_result"]
                embed.description = "🔵 任务成功" if result["succeeded"] else "🔴 任务失败"
                embed.add_field(name="行动牌", value=f"成功 {result['success_count']} · 失败 {result['fail_count']}", inline=False)
            elif status == "ASSASSINATION":
                evil_lines = [
                    f"{_player_line(state, uid)} · {rules.ROLE_NAMES[role]}"
                    for uid, role in state["roles"].items()
                    if rules.side_for_role(role) == rules.EVIL
                ]
                embed.description = "三次任务已经完成。\n刺客，请选择梅林。"
                embed.add_field(name="邪恶阵营", value="\n".join(evil_lines), inline=False)
        elif status == "FINISHED":
            winner = "亚瑟阵营" if state["winner"] == rules.GOOD else "莫德雷德阵营"
            embed.description = f"🏆 **{winner}胜利**\n{state['end_reason']}"
            role_lines = [
                f"{_player_line(state, str(player['id']))} · {rules.ROLE_NAMES[state['roles'][str(player['id'])]]}"
                for player in state["players"]
            ]
            embed.add_field(name="身份揭晓", value="\n".join(role_lines), inline=False)
            embed.add_field(name="任务", value=_quest_track(state), inline=False)
        else:
            embed.description = state.get("end_reason") or "本局已结束。"

        embed.set_footer(text=f"对局 #{state['id']}")
        return embed

    async def _refresh_message(self, state: dict, interaction: discord.Interaction | None = None):
        message = interaction.message if interaction and interaction.message else None
        if message and str(message.id) != str(state.get("message_id")):
            message = None
        if message is None:
            channel = self.bot.get_channel(int(state["channel_id"]))
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(int(state["channel_id"]))
                except discord.HTTPException:
                    return
            try:
                message = await channel.fetch_message(int(state["message_id"]))
            except discord.HTTPException:
                return
        view = None if state["status"] in {"FINISHED", "CANCELLED"} else AvalonGameView(self, state)
        await message.edit(embed=self.build_embed(state), view=view)

    async def _state_for_interaction(self, interaction: discord.Interaction) -> dict | None:
        if not interaction.message:
            return None
        return await asyncio.to_thread(avalon_db.get_game_by_message, interaction.message.id)

    def _is_controller(self, interaction: discord.Interaction, state: dict) -> bool:
        if str(interaction.user.id) == str(state["owner_id"]):
            return True
        return isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_guild

    async def handle_action(self, interaction: discord.Interaction, action: str):
        state = await self._state_for_interaction(interaction)
        if not state:
            return await interaction.response.send_message("这局游戏不存在或已经失效。", ephemeral=True)

        if action == "view_role":
            return await self.show_role(interaction, state["id"])

        if action == "assassinate":
            user_id = str(interaction.user.id)
            if state["status"] != "ASSASSINATION" or state["roles"].get(user_id) != rules.ASSASSIN:
                return await interaction.response.send_message("现在还不能刺杀。", ephemeral=True)
            view = discord.ui.View(timeout=300)
            view.add_item(AvalonAssassinationSelect(self, state["id"], state))
            return await interaction.response.send_message("选择你的目标。", view=view, ephemeral=True)

        if action in {"quest_success", "quest_fail"}:
            choice = "SUCCESS" if action == "quest_success" else "FAIL"
            return await self.submit_quest_choice(interaction, state["id"], choice)

        await interaction.response.defer(ephemeral=True, thinking=False)
        message = await self._apply_simple_action(interaction, state["id"], action)
        await interaction.followup.send(message, ephemeral=True)

    async def _apply_simple_action(self, interaction: discord.Interaction, game_id: int, action: str) -> str:
        async with self._lock(game_id):
            state = await asyncio.to_thread(avalon_db.get_game, game_id)
            if not state:
                return "这局游戏不存在。"
            user_id = str(interaction.user.id)
            player_ids = _player_ids(state)

            if action == "join":
                if state["status"] != "LOBBY":
                    return "游戏已经开始。"
                if user_id in player_ids:
                    return "你已经在大厅中。"
                if len(player_ids) >= 10:
                    return "大厅已满。"
                if interaction.user.bot:
                    return "机器人不能加入游戏。"
                state["players"].append({"id": user_id, "name": interaction.user.display_name})
                message = "已加入阿瓦隆大厅。"
            elif action == "leave":
                if state["status"] != "LOBBY":
                    return "游戏开始后不能退出。"
                if user_id not in player_ids:
                    return "你不在大厅中。"

                state["players"] = [player for player in state["players"] if str(player["id"]) != user_id]
                message = "已退出阿瓦隆大厅。"
            elif action == "start":
                if state["status"] != "LOBBY" or not self._is_controller(interaction, state):
                    return "只有房主能从大厅开始游戏。"
                if len(state["players"]) not in rules.SIDE_COUNTS:
                    return "阿瓦隆需要 5 至 10 名玩家。"
                state["settings"] = rules.automatic_settings(len(state["players"]))
                ok, error = rules.validate_settings(len(state["players"]), state["settings"])
                if not ok:
                    return error
                deck = rules.build_role_deck(len(state["players"]), state["settings"])
                random.SystemRandom().shuffle(state["players"])
                state["roles"] = {
                    str(player["id"]): role for player, role in zip(state["players"], deck, strict=True)
                }
                state["role_viewed"] = []
                state["role_confirmed"] = []
                state["leader_index"] = 0
                state["status"] = "ROLE_CONFIRMATION"
                message = "身份已分配。请查看并确认自己的身份。"
            elif action == "confirm_role":
                if state["status"] != "ROLE_CONFIRMATION" or user_id not in player_ids:
                    return "现在不能确认身份。"
                if user_id not in state["role_viewed"]:
                    return "请先查看自己的身份。"
                if user_id in state["role_confirmed"]:
                    return "你已经确认过身份。"
                state["role_confirmed"].append(user_id)
                if len(state["role_confirmed"]) == len(player_ids):
                    state["status"] = "TEAM_PROPOSAL"
                    message = "身份确认完成，第一任队长开始组队。"
                else:
                    message = "身份已确认。"
            elif action in {"vote_approve", "vote_reject"}:
                if state["status"] != "TEAM_VOTE" or user_id not in player_ids:
                    return "现在不能投票。"
                if user_id in state["votes"]:
                    return "你已经投过票；投票不能修改。"
                state["votes"][user_id] = "APPROVE" if action == "vote_approve" else "REJECT"
                message = "已秘密提交赞成票。" if action == "vote_approve" else "已秘密提交反对票。"
                if len(state["votes"]) == len(player_ids):
                    approvals = sum(value == "APPROVE" for value in state["votes"].values())
                    passed = rules.team_vote_passes(len(player_ids), approvals)
                    state["vote_result"] = {
                        "passed": passed,
                        "approve_count": approvals,
                        "reject_count": len(player_ids) - approvals,
                        "votes": dict(state["votes"]),
                    }
                    state["status"] = "TEAM_VOTE_RESULT"
                    message += " 所有人已完成投票，结果现已公开。"
            elif action == "continue":
                if not self._is_controller(interaction, state):
                    return "只有房主或服务器管理者可以推进公开结果。"
                if state["status"] == "TEAM_VOTE_RESULT":
                    if state["vote_result"]["passed"]:
                        state["status"] = "QUEST_SUBMISSION"
                        state["quest_submissions"] = {}
                        message = "队伍通过，进入任务阶段。"
                    else:
                        state["reject_count"] += 1
                        if state["reject_count"] >= 5:
                            self._finish(
                                state,
                                rules.EVIL,
                                "同一任务连续五次组队被否决。",
                                "FIVE_REJECTIONS",
                            )
                            message = "连续五次组队被否决，坏人获胜。"
                        else:
                            state["leader_index"] = (int(state["leader_index"]) + 1) % len(player_ids)
                            state["proposed_team"] = []
                            state["votes"] = {}
                            state["vote_result"] = None
                            state["status"] = "TEAM_PROPOSAL"
                            message = "队伍被否决，队长顺位移动。"
                elif state["status"] == "QUEST_RESULT":
                    successes = sum(bool(value) for value in state["quest_results"])
                    failures = len(state["quest_results"]) - successes
                    if failures >= 3:
                        self._finish(
                            state,
                            rules.EVIL,
                            "三个任务失败。",
                            "THREE_FAILED_QUESTS",
                        )
                        message = "坏人已破坏三个任务。"
                    elif successes >= 3:
                        state["status"] = "ASSASSINATION"
                        message = "好人完成三个任务，进入刺杀梅林阶段。"
                    else:
                        state["leader_index"] = (int(state["leader_index"]) + 1) % len(player_ids)
                        state["quest_index"] += 1
                        state["reject_count"] = 0
                        state["proposed_team"] = []
                        state["votes"] = {}
                        state["quest_submissions"] = {}
                        state["vote_result"] = None
                        state["quest_result"] = None
                        state["status"] = "TEAM_PROPOSAL"
                        message = "进入下一个任务，队长顺位移动。"
                else:
                    return "当前没有等待推进的公开结果。"
            elif action == "reset":
                if not self._is_controller(interaction, state):
                    return "只有唤醒者或服务器管理者可以清空本局。"
                now = datetime.now(timezone.utc)
                confirmations = state.setdefault("reset_confirmations", {})
                confirmed_at = _parse_iso(confirmations.get(user_id))
                if confirmed_at and confirmed_at.tzinfo is None:
                    confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)
                if confirmed_at and (now - confirmed_at).total_seconds() <= RESET_CONFIRM_SECONDS:
                    state["status"] = "CANCELLED"
                    state["end_reason"] = f"由 {_mention(user_id)} 双击确认清空。"
                    state["reset_confirmations"] = {}
                    message = "本局已清空，可以在本频道重新使用 `&avalon`。"
                else:
                    confirmations[user_id] = now.isoformat()
                    message = "第一次确认已记录；请在 60 秒内再次点击红色“清空 / 重置”按钮。"
            else:
                return "未知操作。"

            _touch(state)
            await asyncio.to_thread(avalon_db.save_game, state)
            if state["status"] == "FINISHED":
                await asyncio.to_thread(avalon_db.record_game_results, state)
            await self._refresh_message(state, interaction)
            return message

    def build_private_role_embed(self, state: dict, user_id: str) -> discord.Embed:
        role = state["roles"][user_id]
        side = rules.side_for_role(role)
        color = 0x3498DB if side == rules.GOOD else 0xE74C3C
        embed = discord.Embed(title=rules.ROLE_NAMES[role], description=ROLE_DESCRIPTIONS[role], color=color)
        embed.add_field(name="阵营", value=rules.SIDE_NAMES[side], inline=False)
        embed.add_field(name="职责", value=ROLE_DUTIES[role], inline=False)
        embed.add_field(name="你看见了", value=_knowledge_text(state, user_id), inline=False)
        embed.set_footer(text="仅你可见")
        return embed

    def _front_asset_key(self, state: dict, user_id: str, role: str) -> str | None:
        variants = ROLE_FRONT_VARIANTS.get(role)
        if not variants:
            return ROLE_ASSET_KEYS.get(role)

        player_order = [
            str(player["id"])
            for player in state.get("players", [])
            if state["roles"].get(str(player["id"])) == role
        ]
        if not player_order:
            player_order = [
                str(candidate_id)
                for candidate_id, candidate_role in state["roles"].items()
                if candidate_role == role
            ]
        try:
            variant_index = player_order.index(str(user_id)) % len(variants)
        except ValueError:
            variant_index = 0
        return variants[variant_index]

    def build_private_role_card_payload(
        self,
        state: dict,
        user_id: str,
        front_variant_index: int | None = None,
    ) -> tuple[list[discord.File], list[discord.Embed]] | None:
        role = state["roles"][user_id]
        asset_key = ROLE_ASSET_KEYS.get(role)
        variants = ROLE_FRONT_VARIANTS.get(role)
        if variants and front_variant_index is not None:
            front_asset_key = variants[front_variant_index % len(variants)]
        else:
            front_asset_key = self._front_asset_key(state, user_id, role)
        if not asset_key or not front_asset_key:
            return None

        front_path = CARD_DIR / f"{front_asset_key}_front.png"
        back_path = CARD_DIR / f"{asset_key}_back.png"
        if not front_path.is_file() or not back_path.is_file():
            return None

        side = rules.side_for_role(role)
        color = 0x3498DB if side == rules.GOOD else 0xE74C3C
        front_name = f"{front_asset_key}_front.png"
        back_name = f"{asset_key}_back.png"
        files = [
            discord.File(front_path, filename=front_name),
            discord.File(back_path, filename=back_name),
        ]

        # Discord groups image-only embeds that share a URL into one gallery row.
        front_embed = discord.Embed(url=ROLE_GALLERY_URL, color=color)
        front_embed.set_image(url=f"attachment://{front_name}")
        back_embed = discord.Embed(url=ROLE_GALLERY_URL, color=color)
        back_embed.set_image(url=f"attachment://{back_name}")

        vision_embed = discord.Embed(
            title="你看见了",
            description=_knowledge_text(state, user_id),
            color=color,
        )
        vision_embed.set_footer(text="仅你可见")
        return files, [front_embed, back_embed, vision_embed]

    async def show_role(self, interaction: discord.Interaction, game_id: int):
        async with self._lock(game_id):
            state = await asyncio.to_thread(avalon_db.get_game, game_id)
            user_id = str(interaction.user.id)
            if not state or user_id not in _player_ids(state) or not state.get("roles"):
                return await interaction.response.send_message("你不是本局玩家，或身份尚未分配。", ephemeral=True)
            if user_id not in state["role_viewed"]:
                state["role_viewed"].append(user_id)
            _touch(state)
            await asyncio.to_thread(avalon_db.save_game, state)
            card_payload = self.build_private_role_card_payload(state, user_id)
            fallback_embed = None if card_payload else self.build_private_role_embed(state, user_id)

        if card_payload:
            files, embeds = card_payload
            await interaction.response.send_message(files=files, embeds=embeds, ephemeral=True)
        else:
            await interaction.response.send_message(embed=fallback_embed, ephemeral=True)

    async def submit_team(self, interaction: discord.Interaction, game_id: int, selected: list[str]):
        await interaction.response.defer(ephemeral=True, thinking=False)
        async with self._lock(game_id):
            state = await asyncio.to_thread(avalon_db.get_game, game_id)
            if not state or state["status"] != "TEAM_PROPOSAL":
                return await interaction.followup.send("当前已经不是组队阶段。", ephemeral=True)
            if str(interaction.user.id) != _leader_id(state):
                return await interaction.followup.send("只有当前队长可以提交队伍。", ephemeral=True)
            expected = rules.quest_team_size(len(state["players"]), int(state["quest_index"]))
            selected = list(dict.fromkeys(str(value) for value in selected))
            if len(selected) != expected or any(uid not in _player_ids(state) for uid in selected):
                return await interaction.followup.send(f"必须选择恰好 {expected} 名本局玩家。", ephemeral=True)
            state["proposed_team"] = selected
            state["votes"] = {}
            state["vote_result"] = None
            state["status"] = "TEAM_VOTE"
            _touch(state)
            await asyncio.to_thread(avalon_db.save_game, state)
            await self._refresh_message(state)
        await interaction.followup.send("队伍已提交，进入全员秘密投票。", ephemeral=True)

    async def submit_quest_choice(self, interaction: discord.Interaction, game_id: int, choice: str):
        await interaction.response.defer(ephemeral=True, thinking=False)
        async with self._lock(game_id):
            state = await asyncio.to_thread(avalon_db.get_game, game_id)
            user_id = str(interaction.user.id)
            if not state or state["status"] != "QUEST_SUBMISSION" or user_id not in state["proposed_team"]:
                return await interaction.followup.send("当前不能提交任务牌。", ephemeral=True)
            if user_id in state["quest_submissions"]:
                return await interaction.followup.send("你已经提交过任务牌。", ephemeral=True)
            if choice not in {"SUCCESS", "FAIL"}:
                return await interaction.followup.send("无效任务牌。", ephemeral=True)
            if choice == "FAIL" and rules.side_for_role(state["roles"][user_id]) != rules.EVIL:
                return await interaction.followup.send("好人必须提交任务成功。", ephemeral=True)

            state["quest_submissions"][user_id] = choice
            finished = len(state["quest_submissions"]) == len(state["proposed_team"])
            if finished:
                fail_count = sum(value == "FAIL" for value in state["quest_submissions"].values())
                success_count = len(state["proposed_team"]) - fail_count
                needed = rules.fails_required(len(state["players"]), int(state["quest_index"]))
                succeeded = rules.quest_succeeds(len(state["players"]), int(state["quest_index"]), fail_count)
                state["quest_result"] = {
                    "success_count": success_count,
                    "fail_count": fail_count,
                    "fails_required": needed,
                    "succeeded": succeeded,
                }
                state["quest_results"].append(succeeded)
                state["status"] = "QUEST_RESULT"
            _touch(state)
            await asyncio.to_thread(avalon_db.save_game, state)
            await self._refresh_message(state)
        text = "任务牌已秘密提交。"
        if finished:
            text += " 所有成员已提交，任务结果现已公开。"
        await interaction.followup.send(text, ephemeral=True)

    async def submit_assassination(self, interaction: discord.Interaction, game_id: int, target_id: str):
        await interaction.response.defer(ephemeral=True, thinking=False)
        async with self._lock(game_id):
            state = await asyncio.to_thread(avalon_db.get_game, game_id)
            user_id = str(interaction.user.id)
            target_id = str(target_id)
            if not state or state["status"] != "ASSASSINATION" or state["roles"].get(user_id) != rules.ASSASSIN:
                return await interaction.followup.send("当前不能执行刺杀。", ephemeral=True)
            if target_id not in _player_ids(state) or rules.side_for_role(state["roles"][target_id]) != rules.GOOD:
                return await interaction.followup.send("刺客必须选择一名好人。", ephemeral=True)
            if state["roles"][target_id] == rules.MERLIN:
                self._finish(
                    state,
                    rules.EVIL,
                    f"刺客 {_mention(user_id)} 成功刺杀了梅林 {_mention(target_id)}。",
                    "ASSASSIN_HIT",
                )
                message = "刺杀命中梅林，坏人获胜。"
            else:
                self._finish(
                    state,
                    rules.GOOD,
                    f"刺客 {_mention(user_id)} 刺杀了 {_mention(target_id)}，但目标不是梅林。",
                    "ASSASSIN_MISSED",
                )
                message = "刺杀失败，好人获胜。"
            _touch(state)
            await asyncio.to_thread(avalon_db.save_game, state)
            await asyncio.to_thread(avalon_db.record_game_results, state)
            await self._refresh_message(state)
        await interaction.followup.send(message, ephemeral=True)

    def _finish(self, state: dict, winner: str, reason: str, win_code: str):
        state["status"] = "FINISHED"
        state["winner"] = winner
        state["end_reason"] = reason
        state["win_code"] = win_code
        state["finished_at"] = _now_iso()

    async def cleanup_inactive_games(self) -> int:
        games = await asyncio.to_thread(avalon_db.list_active_games)
        cleaned = 0
        for summary in games:
            game_id = int(summary["id"])
            async with self._lock(game_id):
                state = await asyncio.to_thread(avalon_db.get_game, game_id)
                if not state or state["status"] not in avalon_db.ACTIVE_STATUSES:
                    continue
                if not is_game_inactive(state):
                    continue
                state["status"] = "CANCELLED"
                state["end_reason"] = "连续 1 小时没有有效交互，已自动清空。"
                state["reset_confirmations"] = {}
                await asyncio.to_thread(avalon_db.save_game, state)
                await self._refresh_message(state)
                cleaned += 1
        return cleaned

    async def inactivity_cleanup_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                cleaned = await self.cleanup_inactive_games()
                if cleaned:
                    print(f"[Avalon] auto-cleaned {cleaned} inactive game(s)")
            except Exception as exc:
                print(f"[Avalon] inactivity cleanup failed: {exc}")
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
