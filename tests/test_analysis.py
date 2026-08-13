import json
import unittest
from pathlib import Path

from dnd_calculator.analysis import (
    analyze_build,
    analyze_encounter,
    analyze_encounter_bundle,
    attack_probabilities,
    expected_damage,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "analysis_compatibility.json"


class AnalysisTests(unittest.TestCase):
    def test_roll_modes_natural_one_and_expanded_critical(self):
        normal = attack_probabilities(15, 5, "normal", 20)
        self.assertAlmostEqual(normal["normal"], 0.5)
        self.assertAlmostEqual(normal["critical"], 0.05)
        self.assertAlmostEqual(normal["hit"], 0.55)
        self.assertAlmostEqual(attack_probabilities(15, 5, "advantage", 20)["hit"], 0.7975)
        self.assertAlmostEqual(attack_probabilities(15, 5, "disadvantage", 20)["hit"], 0.3025)
        self.assertAlmostEqual(attack_probabilities(15, 5, "elven_accuracy", 20)["hit"], 0.908875)

        impossible = attack_probabilities(99, -99, "normal", 19)
        self.assertEqual(impossible["normal"], 0)
        self.assertAlmostEqual(impossible["critical"], 0.1)

    def test_negative_flat_damage_is_clipped_per_outcome(self):
        self.assertAlmostEqual(expected_damage(1, 4, -2), 0.75)
        self.assertEqual(expected_damage(0, 6, -2), 0)

    def test_first_hit_rider_power_attack_and_guaranteed_damage(self):
        build = {
            "id": "build", "name": "测试", "enabled": True,
            "attack_bonus": "5", "attacks_per_round": "2", "roll_mode": "normal",
            "crit_range": "20", "damage_dice_count": "1", "damage_die_sides": "8",
            "damage_bonus": "4", "power_attack": False, "crit_extra_dice": "0",
            "rider_dice_count": "1", "rider_die_sides": "6", "rider_bonus": "0",
            "rider_doubles_on_crit": True, "guaranteed_damage": "2",
        }
        result = analyze_build(build, 15)
        self.assertAlmostEqual(result["damage_per_attack"], 4.9)
        self.assertAlmostEqual(result["rider_damage"], 3.045)
        self.assertAlmostEqual(result["dpr"], 14.845)

        power = analyze_build({**build, "power_attack": True, "rider_dice_count": "0", "guaranteed_damage": "0"}, 15)
        self.assertAlmostEqual(power["hit_probability"], 0.3)
        self.assertAlmostEqual(power["dpr"], 11.55)

    def test_disabled_party_and_zero_effective_dpr(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[0]
        config = fixture["config"]
        config["builds"] = [{**build, "enabled": False} for build in config["builds"]]
        result = analyze_encounter(config)
        self.assertEqual(result["party_build_count"], 0)
        self.assertEqual(result["raw_party_dpr"], 0)
        self.assertIsNone(result["estimated_rounds"])

    def test_shared_json_golden_fixtures(self):
        fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for fixture in fixtures:
            with self.subTest(fixture["name"]):
                actual = analyze_encounter_bundle(fixture["config"], fixture["sensitivity_acs"])
                self.assertEqual(actual, fixture["expected"])

    def test_sensitivity_rejects_out_of_range_ac(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[0]
        with self.assertRaisesRegex(ValueError, "敏感性 AC"):
            analyze_encounter_bundle(fixture["config"], [0])

    def test_malformed_build_is_a_recoverable_validation_error(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[0]
        with self.assertRaisesRegex(ValueError, "构筑方案必须是对象"):
            analyze_encounter({**fixture["config"], "builds": [None]})


if __name__ == "__main__":
    unittest.main()
