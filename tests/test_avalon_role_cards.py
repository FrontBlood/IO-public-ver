import unittest

from PIL import Image

from services import avalon_rules as rules
from services.avalon_service import (
    CARD_DIR,
    ROLE_ASSET_KEYS,
    ROLE_FRONT_VARIANTS,
    AvalonService,
)
from tests.test_avalon_views import game_state


class AvalonRoleCardTests(unittest.TestCase):
    def test_every_role_has_fixed_size_front_and_back(self):
        self.assertEqual(set(ROLE_ASSET_KEYS), set(rules.ROLE_NAMES))
        for role, asset_key in ROLE_ASSET_KEYS.items():
            back_path = CARD_DIR / f"{asset_key}_back.png"
            self.assertTrue(back_path.is_file(), back_path)
            with Image.open(back_path) as image:
                self.assertEqual((1024, 1536), image.size, back_path)

            front_keys = ROLE_FRONT_VARIANTS.get(role, (asset_key,))
            for front_key in front_keys:
                front_path = CARD_DIR / f"{front_key}_front.png"
                self.assertTrue(front_path.is_file(), front_path)
                with Image.open(front_path) as image:
                    self.assertEqual((1024, 1536), image.size, front_path)

    def test_private_payload_contains_parallel_cards_and_vision(self):
        payload = AvalonService(bot=None).build_private_role_card_payload(
            game_state("TEAM_PROPOSAL"), "1"
        )
        self.assertIsNotNone(payload)
        files, embeds = payload
        try:
            self.assertEqual(2, len(files))
            self.assertEqual(3, len(embeds))
            self.assertEqual("你看见了", embeds[-1].title)
            self.assertEqual("4. <@4>\n5. <@5>", embeds[-1].description)
            self.assertTrue(embeds[0].image.url.startswith("attachment://"))
            self.assertTrue(embeds[1].image.url.startswith("attachment://"))
        finally:
            for file in files:
                file.close()

    def test_duplicate_generic_roles_rotate_three_fronts_by_seat(self):
        service = AvalonService(bot=None)
        for role, prefix in (
            (rules.LOYAL_SERVANT, "loyal_servant"),
            (rules.MINION, "minion"),
        ):
            state = game_state("TEAM_PROPOSAL")
            for player in state["players"][:4]:
                state["roles"][str(player["id"])] = role
            names = []
            for user_id in ("1", "2", "3", "4"):
                payload = service.build_private_role_card_payload(state, user_id)
                self.assertIsNotNone(payload)
                files, _ = payload
                names.append(files[0].filename)
                for file in files:
                    file.close()
            self.assertEqual(
                [
                    f"{prefix}_1_front.png", f"{prefix}_2_front.png",
                    f"{prefix}_3_front.png", f"{prefix}_1_front.png",
                ],
                names,
            )


if __name__ == "__main__":
    unittest.main()
