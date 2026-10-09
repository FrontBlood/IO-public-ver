import random
import unittest

from services import avalon_rules as rules
from services.avalon_service import AvalonGameView, AvalonService
from tests.test_avalon_views import game_state


class AvalonAutomaticRoleTests(unittest.IsolatedAsyncioTestCase):
    async def test_lobby_has_no_manual_role_configuration(self):
        state = game_state("LOBBY")
        state["players"] = []
        state["leader_index"] = None
        view = AvalonGameView(AvalonService(bot=None), state)
        custom_ids = {item.custom_id for item in view.children}
        self.assertNotIn("avalon:configure", custom_ids)

    async def test_special_roles_are_selected_automatically_by_player_count(self):
        expected_optional = {
            5: {rules.PERCIVAL, rules.MORGANA},
            6: {rules.PERCIVAL, rules.MORGANA},
            7: {rules.PERCIVAL, rules.MORGANA, rules.OBERON},
            8: {rules.PERCIVAL, rules.MORGANA, rules.MORDRED},
            9: {rules.PERCIVAL, rules.MORGANA, rules.MORDRED},
            10: {rules.PERCIVAL, rules.MORGANA, rules.MORDRED, rules.OBERON},
        }
        ordinary = {rules.LOYAL_SERVANT, rules.MINION, rules.MERLIN, rules.ASSASSIN}
        for player_count, expected in expected_optional.items():
            with self.subTest(player_count=player_count):
                settings = rules.automatic_settings(player_count)
                deck = rules.build_role_deck(player_count, settings, random.Random(1))
                optional = set(deck) - ordinary
                self.assertEqual(expected, optional)


if __name__ == "__main__":
    unittest.main()
