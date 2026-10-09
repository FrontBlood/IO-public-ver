import unittest
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from services.omg_service import (
    OmgInputError,
    build_combo_recommendations,
    build_recommendations,
    process_omg_screenshot,
)
from commands.omg import _format_result
from services.omg_pipeline import (
    COMBO_PAIR_COLOR,
    RECOMMENDATION_BORDER_RED,
    RECOMMENDATION_BORDER_YELLOW,
    draw_combo_links,
    pick_position_tiers,
    recommendation_border_color,
    reticle_arms,
)


def image_bytes(size=(1920, 1080)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "black").save(buffer, format="PNG")
    return buffer.getvalue()


class OmgServiceTest(unittest.TestCase):
    def test_combo_recommendations_require_available_ids_and_rank_by_confidence(self):
        slots = [
            {"status": "ready", "entity_id": "a"},
            {"status": "ready", "entity_id": "b"},
            {"status": "ready", "entity_id": "c"},
        ]
        stats = [
            {"id": "a", "windrun_id": 1, "name": "a", "kind": "ability", "owner_hero_id": 10, "win_rate": 0.50},
            {"id": "b", "windrun_id": 2, "name": "b", "kind": "ability", "owner_hero_id": 20, "win_rate": 0.52},
            {"id": "c", "windrun_id": 3, "name": "c", "kind": "ability", "owner_hero_id": 30, "win_rate": 0.51},
        ]
        pairs = {"data": {"abilityPairs": [
            {"abilityIdOne": 1, "abilityIdTwo": 2, "numPicks": 1000, "wins": 680, "winrate": 0.68},
            {"abilityIdOne": 1, "abilityIdTwo": 3, "numPicks": 600, "wins": 420, "winrate": 0.70},
            {"abilityIdOne": 1, "abilityIdTwo": 99, "numPicks": 5000, "wins": 4000, "winrate": 0.8},
        ]}}
        triplets = {"data": {"abilityTriplets": [
            {"abilityIdOne": 1, "abilityIdTwo": 2, "abilityIdThree": 3, "numPicks": 400, "wins": 276, "winrate": 0.69},
        ]}}
        result = build_combo_recommendations(
            slots, stats, pairs, triplets, {"a": "技能甲", "b": "技能乙", "c": "技能丙"}
        )
        self.assertEqual(result["pairs"][0]["names"], ("技能甲", "技能丙"))
        self.assertEqual(result["pairs"][0]["entity_ids"], ("a", "c"))
        self.assertEqual(len(result["pairs"]), 2)
        self.assertAlmostEqual(result["pairs"][0]["synergy"], 0.195)
        self.assertEqual(result["triplets"][0]["names"], ("技能甲", "技能乙", "技能丙"))

    def test_combo_recommendations_exclude_same_origin_hero(self):
        slots = [{"status": "ready", "entity_id": "model"}, {"status": "ready", "entity_id": "skill"}]
        stats = [
            {"id": "model", "windrun_id": -7, "name": "model", "kind": "model", "win_rate": 0.5},
            {"id": "skill", "windrun_id": 70, "name": "skill", "kind": "ability", "owner_hero_id": 7, "win_rate": 0.5},
        ]
        pairs = {"data": {"abilityPairs": [
            {"abilityIdOne": -7, "abilityIdTwo": 70, "numPicks": 1000, "wins": 700, "winrate": 0.7}
        ]}}
        result = build_combo_recommendations(slots, stats, pairs, {"data": {}}, {})
        self.assertEqual(result["pairs"], ())

    def test_official_chinese_names_cover_every_windrun_entity(self):
        project_root = Path(__file__).resolve().parents[1]
        stats = json.loads(
            (project_root / "assets" / "omg" / "windrun_stats.json").read_text(encoding="utf-8")
        )
        names = json.loads(
            (project_root / "assets" / "omg" / "zh_names.json").read_text(encoding="utf-8")
        )
        entity_ids = {str(item["id"]) for item in stats["items"]}
        self.assertEqual(set(names), entity_ids)
        self.assertEqual(names["largo_catchy_lick"], "动人之舐")
        self.assertEqual(names["largo_frogstomp"], "蛙力千钧")
        self.assertEqual(names["spirit_breaker_charge_of_darkness"], "暗影冲刺")
        self.assertEqual(names["templar_assassin_refraction"], "折光")

    def test_reticle_arms_extend_all_corners_at_45_degrees(self):
        arms = reticle_arms((20, 30, 80, 90), 8, (100, 100))
        self.assertEqual(
            arms,
            [
                ((20, 30), (12, 22)),
                ((80, 30), (88, 22)),
                ((20, 90), (12, 98)),
                ((80, 90), (88, 98)),
            ],
        )
        for start, end in arms:
            self.assertEqual(abs(end[0] - start[0]), abs(end[1] - start[1]))

    def test_draw_combo_links_connects_matching_slot_centers(self):
        image = Image.new("RGB", (1920, 1080), "black")
        slots = [
            {"status": "ready", "entity_id": "a", "bbox": [10, 20, 30, 40]},
            {"status": "ready", "entity_id": "b", "bbox": [90, 100, 110, 120]},
        ]
        draw_combo_links(
            ImageDraw.Draw(image),
            slots,
            {"pairs": ({"entity_ids": ("a", "b")},), "triplets": ()},
            image.size,
        )
        self.assertEqual(image.getpixel((60, 70)), COMBO_PAIR_COLOR)

    def test_formats_combo_recommendations(self):
        text = _format_result(
            {"first": (), "second": (), "third": ()},
            {"pairs": ({"names": ("山崩", "余震"), "win_rate": 0.6723, "synergy": 0.1234, "picks": 1234},), "triplets": ()},
        )
        self.assertIn("双技能：山崩＋余震（胜率 67.2%，协同 +12.3%，样本 1,234）", text)

    def test_recommendation_border_combines_t_and_p_thresholds(self):
        self.assertEqual(recommendation_border_color("T1", "P0"), RECOMMENDATION_BORDER_YELLOW)
        self.assertEqual(recommendation_border_color("T0", "P1"), RECOMMENDATION_BORDER_YELLOW)
        self.assertEqual(recommendation_border_color("T1", "P2"), RECOMMENDATION_BORDER_RED)
        self.assertIsNone(recommendation_border_color("T2", "P0"))
        self.assertIsNone(recommendation_border_color("T0", "P3"))

    def test_pick_position_tier_rewards_earlier_average_pick(self):
        items = [{"id": str(i), "avg_pick": i} for i in range(1, 21)]
        tiers = pick_position_tiers(items)
        self.assertEqual(tiers["1"], "P0")
        self.assertEqual(tiers["2"], "P1")
        self.assertEqual(tiers["20"], "P4")

    def test_recommendations_combine_value_and_pick_tiers_without_duplicates(self):
        slots = [
            {"status": "ready", "tier": "T1", "pick_tier": "P0", "entity_id": "mars"},
            {"status": "ready", "tier": "T0", "pick_tier": "P1", "entity_id": "blade"},
            {"status": "ready", "tier": "T0", "pick_tier": "P2", "entity_id": "late"},
            {"status": "ready", "tier": "T2", "pick_tier": "P0", "entity_id": "early"},
            {"status": "ready", "tier": "T2", "pick_tier": "P2", "entity_id": "balanced"},
            {"status": "ready", "tier": "T1", "pick_tier": "P2", "entity_id": "value"},
            {"status": "ready", "tier": "T1", "pick_tier": "P0", "entity_id": "mars"},
        ]
        result = build_recommendations(
            slots,
            {
                "mars": "马尔斯",
                "blade": "剑刃风暴",
                "late": "严寒灼烧",
                "early": "沟壑",
                "balanced": "星体游魂",
                "value": "午夜凋零",
            },
        )
        self.assertEqual(
            result,
            {
                "first": ("马尔斯",),
                "second": ("剑刃风暴",),
                "third": ("严寒灼烧", "沟壑", "星体游魂", "午夜凋零"),
            },
        )

    def test_formats_ranked_recommendations_and_source(self):
        text = _format_result(
            {"first": ("马尔斯", "影魔"), "second": ("剑刃风暴",), "third": ("星体游魂",)}
        )
        self.assertEqual(
            text,
            "第一推荐（T0/T1＋P0）：马尔斯，影魔\n"
            "第二推荐（T0/T1＋P1）：剑刃风暴\n"
            "第三推荐（T2以上＋P2以上）：星体游魂\n"
            "标注说明：左上 T＝价值评级；右上 P＝抓位评级（P0 最早）\n"
            "数据来源：Windrun API",
        )

    def test_rejects_non_image(self):
        with self.assertRaises(OmgInputError):
            process_omg_screenshot(b"not an image")

    def test_rejects_non_widescreen_image(self):
        with patch("services.omg_service.validate_assets"):
            with self.assertRaisesRegex(OmgInputError, "16:9"):
                process_omg_screenshot(image_bytes((1000, 1000)))


if __name__ == "__main__":
    unittest.main()
