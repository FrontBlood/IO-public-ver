import random
import unittest

from services import avalon_rules as rules


class AvalonRulesTests(unittest.TestCase):
    def test_side_counts_and_mandatory_roles_for_every_player_count(self):
        settings = {
            "percival": True,
            "morgana": True,
            "mordred": False,
            "oberon": False,
        }
        for player_count, (good_count, evil_count) in rules.SIDE_COUNTS.items():
            with self.subTest(player_count=player_count):
                deck = rules.build_role_deck(player_count, settings, random.Random(1))
                self.assertEqual(player_count, len(deck))
                self.assertEqual(good_count, sum(rules.side_for_role(role) == rules.GOOD for role in deck))
                self.assertEqual(evil_count, sum(rules.side_for_role(role) == rules.EVIL for role in deck))
                self.assertIn(rules.MERLIN, deck)
                self.assertIn(rules.ASSASSIN, deck)

    def test_excess_special_roles_are_rejected(self):
        settings = {"percival": True, "morgana": True, "mordred": True, "oberon": True}
        ok, _ = rules.validate_settings(5, settings)
        self.assertFalse(ok)

    def test_team_sizes_match_classic_table(self):
        self.assertEqual((2, 3, 2, 3, 3), rules.QUEST_TEAM_SIZES[5])
        self.assertEqual((2, 3, 3, 4, 4), rules.QUEST_TEAM_SIZES[7])
        self.assertEqual((3, 4, 4, 5, 5), rules.QUEST_TEAM_SIZES[10])

    def test_only_fourth_quest_needs_two_fails_at_seven_plus(self):
        self.assertEqual(2, rules.fails_required(7, 3))
        self.assertEqual(1, rules.fails_required(7, 4))
        self.assertTrue(rules.quest_succeeds(7, 3, 1))
        self.assertFalse(rules.quest_succeeds(7, 3, 2))
        self.assertFalse(rules.quest_succeeds(7, 4, 1))

    def test_tied_team_vote_is_rejected(self):
        self.assertFalse(rules.team_vote_passes(6, 3))
        self.assertTrue(rules.team_vote_passes(6, 4))
        self.assertTrue(rules.team_vote_passes(7, 4))

    def test_merlin_sees_oberon_but_not_mordred(self):
        roles = {
            "1": rules.MERLIN,
            "2": rules.ASSASSIN,
            "3": rules.MORDRED,
            "4": rules.OBERON,
            "5": rules.LOYAL_SERVANT,
        }
        visible = set(rules.knowledge_for_player("1", roles)["visible_players"])
        self.assertEqual({"2", "4"}, visible)

    def test_regular_evil_does_not_see_oberon(self):
        roles = {
            "1": rules.MERLIN,
            "2": rules.ASSASSIN,
            "3": rules.MORDRED,
            "4": rules.OBERON,
            "5": rules.LOYAL_SERVANT,
        }
        visible = set(rules.knowledge_for_player("2", roles)["visible_players"])
        self.assertEqual({"3"}, visible)
        self.assertEqual([], rules.knowledge_for_player("4", roles)["visible_players"])

    def test_percival_sees_unlabelled_merlin_and_morgana_candidates(self):
        roles = {
            "1": rules.MERLIN,
            "2": rules.PERCIVAL,
            "3": rules.MORGANA,
            "4": rules.ASSASSIN,
            "5": rules.LOYAL_SERVANT,
        }
        visible = set(rules.knowledge_for_player("2", roles)["visible_players"])
        self.assertEqual({"1", "3"}, visible)


if __name__ == "__main__":
    unittest.main()
