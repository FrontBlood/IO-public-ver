from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import AsyncMock, patch

import discord

from database import avalon_db
from services.avalon_service import AvalonGameView, AvalonService, is_game_inactive
from tests.test_avalon_views import game_state


class FakePermissions:
    manage_guild = False


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.bot = False
        self.display_name = f"用户{user_id}"
        self.guild_permissions = FakePermissions()


class FakeInteraction:
    def __init__(self, user_id: int):
        self.user = FakeUser(user_id)
        self.message = None


class AvalonCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_active_view_has_red_reset_button(self):
        service = AvalonService(bot=None)
        for status in avalon_db.ACTIVE_STATUSES:
            state = game_state(status)
            if status == "LOBBY":
                state["players"] = []
                state["leader_index"] = None
            view = AvalonGameView(service, state)
            reset = next(item for item in view.children if item.custom_id == "avalon:reset")
            self.assertEqual(discord.ButtonStyle.danger, reset.style)

    async def test_same_controller_must_click_reset_twice(self):
        service = AvalonService(bot=None)
        state = game_state("LOBBY")
        state["owner_id"] = "99"
        state["last_interaction_at"] = datetime.now(timezone.utc).isoformat()
        state["reset_confirmations"] = {}
        interaction = FakeInteraction(99)

        with (
            patch.object(avalon_db, "get_game", return_value=state),
            patch.object(avalon_db, "save_game"),
            patch.object(service, "_refresh_message", new=AsyncMock()),
        ):
            first = await service._apply_simple_action(interaction, state["id"], "reset")
            self.assertEqual("LOBBY", state["status"])
            self.assertIn("第一次确认", first)

            second = await service._apply_simple_action(interaction, state["id"], "reset")
            self.assertEqual("CANCELLED", state["status"])
            self.assertIn("已清空", second)

    async def test_inactivity_threshold_is_exactly_one_hour(self):
        now = datetime.now(timezone.utc)
        state = {"last_interaction_at": (now - timedelta(minutes=59)).isoformat()}
        self.assertFalse(is_game_inactive(state, now))
        state["last_interaction_at"] = (now - timedelta(hours=1)).isoformat()
        self.assertTrue(is_game_inactive(state, now))


if __name__ == "__main__":
    unittest.main()
