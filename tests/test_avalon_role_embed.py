import unittest

from services.avalon_service import AvalonService
from tests.test_avalon_views import game_state


class AvalonRoleEmbedTests(unittest.TestCase):
    def test_private_role_card_contains_identity_side_and_compact_vision(self):
        embed = AvalonService(bot=None).build_private_role_embed(game_state("TEAM_PROPOSAL"), "1")
        self.assertIn("梅林", embed.title)
        fields = {field.name: field.value for field in embed.fields}
        self.assertIn("阵营", fields)
        self.assertIn("职责", fields)
        self.assertIn("你看见了", fields)
        self.assertEqual("4. <@4>\n5. <@5>", fields["你看见了"])
        self.assertIn("仅你可见", embed.footer.text)


if __name__ == "__main__":
    unittest.main()
