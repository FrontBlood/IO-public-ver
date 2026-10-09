import unittest

from services.avalon_service import AvalonService
from tests.test_avalon_views import game_state


class AvalonRoleSummaryTests(unittest.TestCase):
    def test_active_embed_lists_only_special_roles_without_counts(self):
        embed = AvalonService(bot=None).build_embed(game_state("TEAM_PROPOSAL"))
        fields = {field.name: field.value for field in embed.fields}
        self.assertIn("本局角色", fields)
        summary = fields["本局角色"]
        self.assertIn("梅林", summary)
        self.assertIn("刺客", summary)
        self.assertNotIn("忠臣", summary)
        self.assertNotIn("爪牙", summary)
        self.assertNotIn("×", summary)
        self.assertIn("邪恶阵营：2 人", summary)


if __name__ == "__main__":
    unittest.main()
