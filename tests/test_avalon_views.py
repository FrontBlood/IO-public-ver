import unittest

from services import avalon_rules as rules
from services.avalon_service import AvalonGameView, AvalonService


def game_state(status: str) -> dict:
    players = [{"id": str(index), "name": f"玩家{index}"} for index in range(1, 6)]
    return {
        "id": 1,
        "guild_id": "100",
        "channel_id": "200",
        "message_id": "300",
        "owner_id": "99",
        "status": status,
        "players": players,
        "settings": {"percival": True, "morgana": True, "mordred": False, "oberon": False},
        "roles": {
            "1": rules.MERLIN,
            "2": rules.PERCIVAL,
            "3": rules.LOYAL_SERVANT,
            "4": rules.ASSASSIN,
            "5": rules.MORGANA,
        },
        "role_viewed": [],
        "role_confirmed": [],
        "leader_index": 0,
        "quest_index": 0,
        "reject_count": 0,
        "quest_results": [],
        "proposed_team": ["1", "2"],
        "votes": {},
        "quest_submissions": {},
        "vote_result": {
            "passed": True,
            "approve_count": 3,
            "reject_count": 2,
            "votes": {"1": "APPROVE", "2": "APPROVE", "3": "APPROVE", "4": "REJECT", "5": "REJECT"},
        },
        "quest_result": {"success_count": 2, "fail_count": 0, "fails_required": 1, "succeeded": True},
        "winner": None,
        "end_reason": None,
    }


class AvalonViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_active_phase_builds_a_persistent_view(self):
        service = AvalonService(bot=None)
        statuses = (
            "LOBBY", "ROLE_CONFIRMATION", "TEAM_PROPOSAL", "TEAM_VOTE",
            "TEAM_VOTE_RESULT", "QUEST_SUBMISSION", "QUEST_RESULT", "ASSASSINATION",
        )
        for status in statuses:
            with self.subTest(status=status):
                state = game_state(status)
                if status == "LOBBY":
                    state["leader_index"] = None
                    state["players"] = []
                view = AvalonGameView(service, state)
                self.assertIsNone(view.timeout)
                self.assertTrue(view.children)

    async def test_common_and_phase_controls_use_separate_rows(self):
        view = AvalonGameView(AvalonService(bot=None), game_state("TEAM_VOTE"))
        rows = {item.custom_id: item.row for item in view.children}
        self.assertEqual(0, rows["avalon:view_role"])
        self.assertEqual(0, rows["avalon:reset"])
        self.assertEqual(1, rows["avalon:vote_approve"])
        self.assertEqual(1, rows["avalon:vote_reject"])

    async def test_team_phase_contains_public_select_and_role_button(self):
        view = AvalonGameView(AvalonService(bot=None), game_state("TEAM_PROPOSAL"))
        custom_ids = {item.custom_id for item in view.children}
        self.assertIn("avalon:view_role", custom_ids)
        self.assertIn("avalon:team_select", custom_ids)

    async def test_quest_phase_contains_direct_result_buttons(self):
        view = AvalonGameView(AvalonService(bot=None), game_state("QUEST_SUBMISSION"))
        custom_ids = {item.custom_id for item in view.children}
        self.assertIn("avalon:quest_success", custom_ids)
        self.assertIn("avalon:quest_fail", custom_ids)

    async def test_main_embed_uses_compact_public_labels(self):
        embed = AvalonService(bot=None).build_embed(game_state("TEAM_PROPOSAL"))
        fields = {field.name: field.value for field in embed.fields}
        self.assertIn("座次", fields)
        self.assertNotIn("随机座次", fields)
        self.assertIn("任务", fields)
        self.assertNotRegex(fields["任务"], r"[1-5]")
        self.assertIn("否决", fields)
        self.assertIn("队长", fields)
        self.assertIn("队伍", fields)


if __name__ == "__main__":
    unittest.main()
