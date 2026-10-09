import random

import discord

from services import avalon_rules as rules
from services.avalon_service import (
    ROLE_FRONT_VARIANTS,
    AvalonService,
    action_specs_for_state,
)


TEST_TIMEOUT_SECONDS = 60 * 60
SCENES = (
    ("招募", "LOBBY"),
    ("确认身份", "ROLE_CONFIRMATION"),
    ("队长组队", "TEAM_PROPOSAL"),
    ("队伍投票", "TEAM_VOTE"),
    ("投票通过", "TEAM_VOTE_RESULT_APPROVED"),
    ("投票否决", "TEAM_VOTE_RESULT_REJECTED"),
    ("执行任务", "QUEST_SUBMISSION"),
    ("任务成功", "QUEST_RESULT_SUCCESS"),
    ("任务失败", "QUEST_RESULT_FAIL"),
    ("刺杀梅林", "ASSASSINATION"),
    ("好人结算", "FINISHED_GOOD"),
    ("坏人结算", "FINISHED_EVIL"),
)


class AvalonRolePreviewSelect(discord.ui.Select):
    def __init__(self, panel):
        self.panel = panel
        options = []
        for role in rules.ROLE_NAMES:
            variants = ROLE_FRONT_VARIANTS.get(role)
            if variants:
                options.extend(
                    discord.SelectOption(
                        label=f"{rules.ROLE_NAMES[role]} · 形象 {index + 1}",
                        value=f"{role}:{index}",
                        description=rules.SIDE_NAMES[rules.side_for_role(role)],
                    )
                    for index in range(len(variants))
                )
            else:
                options.append(
                    discord.SelectOption(
                        label=rules.ROLE_NAMES[role],
                        value=role,
                        description=rules.SIDE_NAMES[rules.side_for_role(role)],
                    )
                )
        super().__init__(
            placeholder="选择一张角色卡",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.panel.preview_role(interaction, self.values[0])


class AvalonRolePreviewView(discord.ui.View):
    def __init__(self, panel):
        super().__init__(timeout=300)
        self.add_item(AvalonRolePreviewSelect(panel))


class AvalonTestActionButton(discord.ui.Button):
    def __init__(self, panel, action, label, style, row):
        super().__init__(
            label=label,
            style=style,
            custom_id=f"avalon:test:{action}",
            row=row,
        )
        self.panel = panel
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if self.action == "view_role":
            return await interaction.response.send_message(
                "选择一张身份卡查看。",
                view=AvalonRolePreviewView(self.panel),
                ephemeral=True,
            )
        feedback = {
            "join": "正式对局中，你会加入当前大厅。",
            "leave": "正式对局中，你会退出当前大厅。",
            "start": "正式对局中，房主会结束招募并分配身份。",
            "reset": "正式对局需要在 60 秒内再次点击确认清空。",
            "confirm_role": "身份确认已提交。",
            "vote_approve": "赞成票已秘密提交。",
            "vote_reject": "反对票已秘密提交。",
            "continue": "公开结果确认后，游戏进入下一阶段。",
            "quest_success": "任务成功牌已秘密提交。",
            "quest_fail": "任务失败牌已秘密提交。",
            "assassinate": "正式对局中，仅刺客会看到目标选择菜单。",
        }
        await interaction.response.send_message(
            feedback.get(self.action, "测试交互已触发。"),
            ephemeral=True,
        )


class AvalonTestTeamSelect(discord.ui.Select):
    def __init__(self, panel, state):
        size = rules.quest_team_size(len(state["players"]), int(state["quest_index"]))
        super().__init__(
            placeholder=f"选择 {size} 名任务成员",
            min_values=size,
            max_values=size,
            options=[
                discord.SelectOption(label=player["name"], value=str(player["id"]))
                for player in state["players"]
            ],
            row=1,
        )
        self.panel = panel

    async def callback(self, interaction: discord.Interaction):
        names = [
            next(player["name"] for player in self.panel.state["players"] if player["id"] == value)
            for value in self.values
        ]
        await interaction.response.send_message(
            "已选择：\n" + "\n".join(names),
            ephemeral=True,
        )


class AvalonTestNavButton(discord.ui.Button):
    def __init__(self, panel, action, label, style=discord.ButtonStyle.secondary):
        super().__init__(
            label=label,
            style=style,
            custom_id=f"avalon:test-nav:{action}",
            row=4,
        )
        self.panel = panel
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        await self.panel.navigate(interaction, self.action)


class AvalonTestView(discord.ui.View):
    def __init__(
        self,
        service: AvalonService,
        owner_id: int,
        player_count: int | None = None,
        scene_index: int = 0,
    ):
        super().__init__(timeout=TEST_TIMEOUT_SECONDS)
        self.service = service
        self.owner_id = int(owner_id)
        self.message = None
        self.scene_index = scene_index % len(SCENES)
        self.randomize(player_count)
        self._build_items()

    def randomize(self, player_count: int | None = None):
        rng = random.SystemRandom()
        self.player_count = player_count or rng.randint(5, 10)
        settings = rules.automatic_settings(self.player_count)
        deck = rules.build_role_deck(self.player_count, settings, rng=rng)
        self.players = [
            {
                "id": f"sim_{index + 1}",
                "name": f"模拟玩家 {index + 1}",
                "simulated": True,
            }
            for index in range(self.player_count)
        ]
        self.roles = {
            player["id"]: role
            for player, role in zip(self.players, deck, strict=True)
        }
        self.leader_index = rng.randrange(self.player_count)

    def _make_state(self) -> dict:
        _, scene = SCENES[self.scene_index]
        status = scene.split("_APPROVED")[0].split("_REJECTED")[0]
        status = status.split("_SUCCESS")[0].split("_FAIL")[0]
        status = status.split("_GOOD")[0].split("_EVIL")[0]
        ids = [player["id"] for player in self.players]
        quest_index = 1
        team_size = rules.quest_team_size(self.player_count, quest_index)
        proposed_team = ids[:team_size]
        votes = {
            user_id: ("APPROVE" if index < (self.player_count // 2 + 1) else "REJECT")
            for index, user_id in enumerate(ids)
        }
        state = {
            "id": "TEST",
            "owner_id": ids[0],
            "status": status,
            "players": self.players,
            "roles": self.roles,
            "settings": rules.automatic_settings(self.player_count),
            "role_viewed": ids[:2],
            "role_confirmed": ids[:2],
            "leader_index": self.leader_index,
            "quest_index": quest_index,
            "reject_count": 2,
            "quest_results": [True],
            "proposed_team": proposed_team,
            "votes": votes if status in {"TEAM_VOTE", "TEAM_VOTE_RESULT"} else {},
            "quest_submissions": (
                {user_id: "SUCCESS" for user_id in proposed_team[:-1]}
                if status == "QUEST_SUBMISSION"
                else {}
            ),
            "vote_result": None,
            "quest_result": None,
            "winner": None,
            "end_reason": None,
        }
        if scene == "TEAM_VOTE_RESULT_APPROVED":
            state["vote_result"] = {
                "passed": True,
                "votes": votes,
                "approve_count": sum(value == "APPROVE" for value in votes.values()),
                "reject_count": sum(value == "REJECT" for value in votes.values()),
            }
        elif scene == "TEAM_VOTE_RESULT_REJECTED":
            rejected_votes = {user_id: "REJECT" for user_id in ids}
            state["vote_result"] = {
                "passed": False,
                "votes": rejected_votes,
                "approve_count": 0,
                "reject_count": self.player_count,
            }
        elif scene == "QUEST_RESULT_SUCCESS":
            state["quest_result"] = {
                "succeeded": True,
                "success_count": team_size,
                "fail_count": 0,
            }
            state["quest_results"] = [True, True]
        elif scene == "QUEST_RESULT_FAIL":
            state["quest_result"] = {
                "succeeded": False,
                "success_count": team_size - 1,
                "fail_count": 1,
            }
            state["quest_results"] = [True, False]
        elif scene == "ASSASSINATION":
            state["quest_results"] = [True, True, True]
        elif scene == "FINISHED_GOOD":
            state["winner"] = rules.GOOD
            state["end_reason"] = "刺客没有找到梅林。"
            state["win_code"] = "ASSASSIN_MISSED"
            state["quest_results"] = [True, False, True, True]
        elif scene == "FINISHED_EVIL":
            state["winner"] = rules.EVIL
            state["end_reason"] = "三个任务失败。"
            state["win_code"] = "THREE_FAILED_QUESTS"
            state["quest_results"] = [False, True, False, False]
        return state

    def _build_items(self):
        self.clear_items()
        self.state = self._make_state()
        for action, label, style, row in action_specs_for_state(self.state):
            if action == "team_select":
                self.add_item(AvalonTestTeamSelect(self, self.state))
            else:
                self.add_item(AvalonTestActionButton(self, action, label, style, row))
        self.add_item(AvalonTestNavButton(self, "previous", "上一阶段"))
        self.add_item(AvalonTestNavButton(self, "next", "下一阶段", discord.ButtonStyle.primary))
        self.add_item(AvalonTestNavButton(self, "reroll", "重随人数"))
        self.add_item(AvalonTestNavButton(self, "cards", "角色卡"))
        self.add_item(AvalonTestNavButton(self, "close", "关闭", discord.ButtonStyle.danger))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        is_admin = (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.manage_guild
        )
        if int(interaction.user.id) == self.owner_id or is_admin:
            return True
        await interaction.response.send_message("只有测试面板创建者或管理员可以操作。", ephemeral=True)
        return False

    def build_embed(self) -> discord.Embed:
        embed = self.service.build_embed(self.state)
        scene_name = SCENES[self.scene_index][0]
        embed.title = f"🧪 {embed.title} · {scene_name}"
        embed.set_footer(
            text=f"测试场景 {self.scene_index + 1}/{len(SCENES)} · 不写入对局与战绩"
        )
        return embed

    def _preview_state(self, selected_role: str) -> dict:
        owner_key = str(self.owner_id)
        remaining = list(self.roles.values())
        if selected_role in remaining:
            remaining.remove(selected_role)
        else:
            selected_side = rules.side_for_role(selected_role)
            replacement = next(
                role for role in remaining if rules.side_for_role(role) == selected_side
            )
            remaining.remove(replacement)
        preview_players = [
            {"id": owner_key, "name": "你", "simulated": True},
            *self.players[1:],
        ]
        roles = {owner_key: selected_role}
        roles.update(
            {
                player["id"]: role
                for player, role in zip(preview_players[1:], remaining, strict=True)
            }
        )
        return {"players": preview_players, "roles": roles}

    async def preview_role(self, interaction: discord.Interaction, selection: str):
        role, separator, variant_text = selection.partition(":")
        variant_index = int(variant_text) if separator else None
        payload = self.service.build_private_role_card_payload(
            self._preview_state(role),
            str(self.owner_id),
            front_variant_index=variant_index,
        )
        if payload is None:
            return await interaction.response.send_message(
                "对应角色卡资产缺失，请检查部署文件。",
                ephemeral=True,
            )
        files, embeds = payload
        await interaction.response.send_message(files=files, embeds=embeds, ephemeral=True)

    async def navigate(self, interaction: discord.Interaction, action: str):
        if action == "cards":
            return await interaction.response.send_message(
                "选择一张身份卡查看。",
                view=AvalonRolePreviewView(self),
                ephemeral=True,
            )
        if action == "close":
            embed = self.build_embed()
            embed.description = "测试面板已关闭。"
            embed.color = 0x7F8C8D
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
            return
        if action == "previous":
            self.scene_index = (self.scene_index - 1) % len(SCENES)
        elif action == "next":
            self.scene_index = (self.scene_index + 1) % len(SCENES)
        elif action == "reroll":
            self.randomize()
        self._build_items()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


async def send_avalon_test_panel(ctx, service: AvalonService):
    view = AvalonTestView(service, ctx.author.id)
    message = await ctx.send(embed=view.build_embed(), view=view)
    view.message = message
