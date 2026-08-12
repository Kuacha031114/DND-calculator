import json
import unittest
from pathlib import Path

from dnd_calculator.application import (
    attack_group_from_entry,
    default_entry,
    normalize_config,
    targets_from_config,
)
from dnd_calculator.models import ApplicationScope


class ApplicationAdapterTests(unittest.TestCase):
    @staticmethod
    def assert_deep_subset(actual, expected):
        if isinstance(expected, dict):
            for key, value in expected.items():
                ApplicationAdapterTests.assert_deep_subset(actual[key], value)
        elif isinstance(expected, list):
            for index, value in enumerate(expected):
                ApplicationAdapterTests.assert_deep_subset(actual[index], value)
        else:
            assert actual == expected

    def test_shared_config_compatibility_fixtures(self):
        fixture_path = Path(__file__).parent / "fixtures" / "config_compatibility.json"
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
        for case in fixtures["valid_cases"]:
            with self.subTest(case=case["name"]):
                normalized = normalize_config(case["input"])
                self.assert_deep_subset(normalized, case["expected"])
        for case in fixtures["invalid_cases"]:
            with self.subTest(case=case["name"]):
                with self.assertRaisesRegex(ValueError, case["error"]):
                    normalize_config(case["input"])

    def test_old_config_is_normalized_without_losing_unknown_data(self):
        config = normalize_config(
            {
                "config_version": 1,
                "future_field": {"keep": True},
                "quick": {"target_ac": "18"},
                "targets": [{"id": "target", "name": "旧目标", "ac": "17"}],
                "entries": [{"id": "entry", "name": "旧攻击", "target_id": "target"}],
            }
        )
        self.assertEqual(config["future_field"], {"keep": True})
        self.assertEqual(config["quick"]["target_ac"], "18")
        self.assertEqual(config["entries"][0]["manual_critical_count"], "0")
        self.assertIn("力量", config["targets"][0]["saves"])

    def test_missing_target_reference_uses_first_target(self):
        config = normalize_config(
            {
                "config_version": 1,
                "targets": [{"id": "target", "name": "目标", "ac": "15"}],
                "entries": [{"id": "entry", "target_id": "missing"}],
            }
        )
        self.assertEqual(config["entries"][0]["target_id"], "target")

    def test_unsupported_config_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不支持配置版本"):
            normalize_config({"config_version": 99})

    def test_shared_adapter_matches_advanced_rules(self):
        entry = default_entry()
        entry.update(
            target_id="target",
            count="2",
            power_indices="2",
            rider="偷袭",
            rider_dice="3",
            damage_type="穿刺",
        )
        group = attack_group_from_entry(entry)
        self.assertEqual(group.power_attack_indices, frozenset({1}))
        self.assertEqual(group.components[1].scope, ApplicationScope.ONCE_SELECTABLE)
        self.assertEqual(group.components[1].damage_type, "穿刺")

    def test_targets_adapter_keeps_defenses(self):
        config = normalize_config(
            {
                "config_version": 1,
                "targets": [{
                    "id": "target", "name": "目标", "ac": "16",
                    "resistances": "火焰，寒冷", "fixed_reduction": "3",
                }],
            }
        )
        target = targets_from_config(config["targets"])[0]
        self.assertEqual(target.ac, 16)
        self.assertEqual(target.resistances, frozenset({"火焰", "寒冷"}))
        self.assertEqual(target.reductions[0].amount, 3)


if __name__ == "__main__":
    unittest.main()
