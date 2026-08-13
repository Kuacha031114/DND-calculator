import json
import unittest

from dnd_calculator.application import default_config
from dnd_calculator.engine import RulesEngine, RulesError
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
        )
        config["entries"][0]["damage_components"].append({
            "id": "sneak", "name": "偷袭", "dice_count": "1", "dice_sides": "6",
            "flat_bonus": "0", "damage_type": "穿刺", "scope": "once_selectable",
            "crit_behavior": "double_dice", "weapon_die": False, "magical": False,
        })
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

    def test_analysis_success_and_validation_error(self):
        config = default_config()["analysis"]
        result = WebBridge.resolve_analysis({"config": config, "sensitivity_acs": [14, 15]})
        self.assertEqual([item["ac"] for item in result["sensitivity"]], [14, 15])
        self.assertEqual(len(result["result"]["builds"]), 2)

        response = json.loads(dispatch_json("resolveAnalysis", json.dumps({
            "config": {**config, "target_ac": "bad"}, "sensitivity_acs": [],
        })))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["type"], "ValueError")
        self.assertIn("目标 AC 必须是整数", response["error"]["message"])

    def test_analysis_rejects_malformed_batch(self):
        with self.assertRaisesRegex(ValueError, "敏感性 AC 必须是数组"):
            WebBridge.resolve_analysis({
                "config": default_config()["analysis"], "sensitivity_acs": "15",
            })

    def test_disposed_session_is_rejected(self):
        bridge = WebBridge()
        started = bridge.start_advanced(default_config())
        bridge.dispose_session(started["session_id"])
        with self.assertRaisesRegex(RulesError, "结算会话不存在"):
            bridge.resolve_attack_damage(started["session_id"])

    def test_unknown_rider_attack_is_rejected(self):
        config = default_config()
        config["entries"][0]["manual_hits"] = True
        config["entries"][0]["damage_components"].append({
            "id": "sneak", "name": "偷袭", "dice_count": "1", "dice_sides": "6",
            "flat_bonus": "0", "damage_type": "穿刺", "scope": "once_selectable",
            "crit_behavior": "double_dice", "weapon_die": False, "magical": False,
        })
        bridge = WebBridge(RulesEngine(SequenceRng([])))
        started = bridge.start_advanced(config)
        component_id = started["selectable_riders"][0]["component_id"]
        with self.assertRaisesRegex(RulesError, "只能选择已命中的攻击"):
            bridge.resolve_attack_damage(started["session_id"], {component_id: ["missing"]})

    def test_selectable_attack_modifier_stage_precedes_damage_riders(self):
        config = default_config()
        entry = config["entries"][0]
        entry["attack_bonus"] = "2"
        entry["attack_modifiers"] = [{
            "id": "bond", "name": "勇气联结", "dice_count": "1", "dice_sides": "4",
            "sign": "1", "scope": "once_selectable",
        }]
        entry["damage_components"].append({
            "id": "smite", "name": "至圣斩", "dice_count": "2", "dice_sides": "8",
            "flat_bonus": "0", "damage_type": "光耀", "scope": "selected_hits",
            "crit_behavior": "double_dice", "weapon_die": False, "magical": True,
        })
        bridge = WebBridge(RulesEngine(SequenceRng([10, 4])))
        started = bridge.start_advanced(config)
        self.assertFalse(started["attack_modifiers_resolved"])
        self.assertEqual(started["selectable_riders"], [])
        attack_id = started["selectable_attack_modifiers"][0]["attacks"][0]["attack_id"]
        resolved = bridge.resolve_attack_modifiers(started["session_id"], {"bond": attack_id})
        self.assertTrue(resolved["attack_modifiers_resolved"])
        self.assertEqual(len(resolved["selectable_riders"]), 1)

    def test_invalid_reroll_references_are_rejected(self):
        config = default_config()
        config["entries"][0].update(manual_hits=True)
        bridge = WebBridge(RulesEngine(SequenceRng([6])))
        started = bridge.start_advanced(config)
        resolved = bridge.resolve_attack_damage(started["session_id"])
        with self.assertRaisesRegex(ValueError, "必须包含来源"):
            bridge.reroll(started["session_id"], [["too", "short"]])
        with self.assertRaisesRegex(RulesError, "重骰引用不存在"):
            bridge.reroll(resolved["session_id"], [["missing", "missing", 0]])

    def test_dispatch_serializes_malformed_reroll_error(self):
        response = json.loads(dispatch_json("reroll", json.dumps({
            "session_id": "missing", "references": [["short"]],
        })))
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
