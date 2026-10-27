import unittest

from nail_knowledge import HAND_TYPES, KNOWLEDGE_VERSION, PALETTE_BY_ID, build_plan, normalize_profile, style_knowledge


def style(title, price, likes=10, **overrides):
    value = {
        "id": likes,
        "title": title,
        "category": "法式",
        "tags": ["法式", "通勤"],
        "scene": "通勤",
        "skin_tones": ["暖黄皮", "自然肤色"],
        "nail_shapes": ["方圆甲", "短甲"],
        "price": price,
        "color_a": "#D9B6A7",
        "color_b": "#E7B9C7",
        "maintenance_ease": 5,
        "likes": likes,
    }
    value.update(overrides)
    return value


class RecommendationTests(unittest.TestCase):
    def test_knowledge_catalog_has_required_reference_data(self):
        self.assertEqual(len(HAND_TYPES), 6)
        self.assertEqual(len(PALETTE_BY_ID), 24)
        metadata = style_knowledge(style("测试款", "79-159"))
        self.assertEqual(metadata["version"], KNOWLEDGE_VERSION)
        self.assertTrue(metadata["sources"])
        self.assertTrue(metadata["color_ids"])

    def test_legacy_profile_is_normalized(self):
        profile = normalize_profile({"skin_tone": "自然肤色", "hand_shape": "短指型", "nail_shape": "短甲", "scene": "宴会"})
        self.assertEqual(profile["skin_tone"], "自然黄皮")
        self.assertEqual(profile["hand_shape"], "短粗手")
        self.assertEqual(profile["nail_shape"], "方圆形")
        self.assertEqual(profile["target_length"], "短")
        self.assertEqual(profile["scene"], "聚会")

    def test_budget_prefers_in_range_style(self):
        plan = build_plan([style("预算内", "79-159", 1), style("超预算", "189-299", 99)], {
            "skin_tone": "黄白皮", "hand_shape": "肉肉手", "nail_shape": "方圆形", "scene": "通勤", "budget_range": "100以内",
        })
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["items"][0]["style"]["title"], "预算内")
        self.assertTrue(plan["items"][0]["in_budget"])

    def test_safety_flag_stops_regular_recommendations(self):
        plan = build_plan([style("测试款", "79-159")], {"safety_flag": True})
        self.assertEqual(plan["status"], "safety_hold")
        self.assertEqual(plan["items"], [])
        self.assertIn("不提供诊断", plan["safety_notice"])


if __name__ == "__main__":
    unittest.main()
