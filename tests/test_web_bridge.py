import json
import unittest

from dnd_calculator.application import default_config
from dnd_calculator.engine import RulesEngine
from dnd_calculator.web_bridge import WebBridge, dispatch_json


class SequenceRng:
    def __init__(self, values):
        self.values = iter(values)

    def randint(self, _minimum, _maximum):
        return next(self.values)


class WebBridgeTests(unittest.TestCase):
    def test_quick_json_matches_engine_result(self):
        bridge = WebBridge(RulesEngine(SequenceRng([15, 6])))
        result = bridge.resolve_quick(
            {
                "target_ac": 15,
                "attack_bonus": 5,
                "attack_count": 1,
                "roll_mode": "normal",
                "damage_dice_count": 1,
                "damage_die_sides": 8,
                "damage_bonus": 3,
            }
        )
        self.assertEqual(result["hit_count"], 1)
        self.assertEqual(result["total_damage"], 9)
        self.assertEqual(result["session"]["mode"], "attack")

    def test_manual_quick_request_does_not_roll_d20(self):
        bridge = WebBridge(RulesEngine(SequenceRng([4, 5])))
        result = bridge.resolve_quick(
            {
                "target_ac": 10,
                "attack_bonus": 99,
                "attack_count": 3,
                "manual_hit_count": 2,
                "manual_critical_count": 0,
                "damage_dice_count": 1,
                "damage_die_sides": 8,
                "damage_bonus": 2,
            }
        )
        self.assertEqual(result["hit_count"], 2)
        self.assertEqual(result["total_damage"], 13)
        self.assertEqual(result["session"]["attack_results"][0]["d20_rolls"], [])

    def test_advanced_session_damage_and_dispose(self):
        config = default_config()
        config["targets"][0]["id"] = "target"
        config["entries"][0].update(
            id="attack",
            target_id="target",
            count="1",
            attack_bonus="5",
            rider="偷袭",
            rider_dice="1",
            dice_count="1",
            dice_sides="8",
            flat_bonus="3",
        )
        bridge = WebBridge(RulesEngine(SequenceRng([15, 6, 4])))
        started = bridge.start_advanced(config)
        self.assertEqual(len(started["selectable_riders"]), 1)
        attack_id = started["selectable_riders"][0]["attacks"][0]["attack_id"]
        component_id = started["selectable_riders"][0]["component_id"]
        resolved = bridge.resolve_attack_damage(
            started["session_id"], {component_id: [attack_id]}
        )
        self.assertEqual(resolved["sessions"][0]["damage_results"][0]["total"], 13)
        self.assertTrue(bridge.dispose_session(started["session_id"])["disposed"])
        self.assertFalse(bridge.dispose_session(started["session_id"])["disposed"])

    def test_dispatch_returns_structured_error(self):
        response = json.loads(dispatch_json("unknown", "{}"))
        self.assertFalse(response["ok"])
        self.assertIn("未知网页桥接方法", response["error"]["message"])


if __name__ == "__main__":
    unittest.main()
