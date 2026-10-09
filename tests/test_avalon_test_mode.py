import unittest
from collections import Counter

from services import avalon_rules as rules
from services.avalon_service import AvalonService
from services.avalon_test_mode import (
    SCENES,
    AvalonRolePreviewSelect,
    AvalonRolePreviewView,
    AvalonTestView,
)


class AvalonTestModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_random_mode_always_uses_five_to_ten_players(self):
        for _ in range(30):
            view = AvalonTestView(AvalonService(bot=None), owner_id=42)
            self.assertGreaterEqual(view.player_count, 5)
            self.assertLessEqual(view.player_count, 10)
            self.assertEqual(view.player_count, len(view.roles))
            view.stop()

    async def test_each_player_count_uses_automatic_role_configuration(self):
        for player_count in range(5, 11):
            view = AvalonTestView(AvalonService(bot=None), owner_id=42, player_count=player_count)
            expected = rules.build_role_deck(
                player_count, rules.automatic_settings(player_count)
            )
            self.assertEqual(Counter(expected), Counter(view.roles.values()))
            view.stop()

    async def test_every_scene_builds_production_embed_and_controls(self):
        view = AvalonTestView(AvalonService(bot=None), owner_id=42, player_count=7)
        for index, (name, _) in enumerate(SCENES):
            with self.subTest(scene=name):
                view.scene_index = index
                view._build_items()
                embed = view.build_embed()
                self.assertIn(name, embed.title)
                self.assertIn(f"{index + 1}/{len(SCENES)}", embed.footer.text)
                self.assertTrue(any(item.row == 4 for item in view.children))
        view.stop()

    async def test_preview_menu_exposes_all_twelve_fronts(self):
        panel = AvalonTestView(AvalonService(bot=None), owner_id=42, player_count=5)
        picker = AvalonRolePreviewView(panel)
        select = next(item for item in picker.children if isinstance(item, AvalonRolePreviewSelect))
        self.assertEqual(12, len(select.options))
        values = {option.value for option in select.options}
        self.assertIn(f"{rules.LOYAL_SERVANT}:2", values)
        self.assertIn(f"{rules.MINION}:2", values)
        panel.stop()
        picker.stop()

    async def test_preview_assigns_selected_role_to_controller(self):
        view = AvalonTestView(AvalonService(bot=None), owner_id=42, player_count=5)
        selected = next(iter(view.roles.values()))
        state = view._preview_state(selected)
        self.assertEqual(selected, state["roles"]["42"])
        self.assertEqual(5, len(state["roles"]))
        self.assertTrue(all(player.get("simulated") for player in state["players"]))
        view.stop()


if __name__ == "__main__":
    unittest.main()
