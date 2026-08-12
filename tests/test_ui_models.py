import unittest

from dnd_calculator.models import ApplicationScope, RollMode
from dnd_calculator.quick import QuickAttackRequest
from dnd_calculator.ui import (
    MODE_LABELS,
    CalculatorApp,
    default_entry,
    default_target,
    entry_display_values,
    normalize_entry,
)


class UiModelTests(unittest.TestCase):
    def app_without_tk(self):
        return CalculatorApp.__new__(CalculatorApp)

    def test_default_entry_builds_without_tk(self):
        entry = default_entry()
        entry["target_id"] = "target"
        group = self.app_without_tk()._attack_group(entry)
        self.assertEqual(group.count, 1)
        self.assertEqual(group.components[0].damage_type, "挥砍")

    def test_per_attack_power_indices_are_one_based_in_ui(self):
        entry = default_entry()
        entry.update(target_id="target", count="3", power_indices="1, 3")
        group = self.app_without_tk()._attack_group(entry)
        self.assertEqual(group.power_attack_indices, frozenset({0, 2}))

    def test_sneak_attack_uses_weapon_damage_type_and_is_selectable(self):
        entry = default_entry()
        entry.update(target_id="target", rider="偷袭", damage_type="穿刺", rider_dice="3")
        group = self.app_without_tk()._attack_group(entry)
        rider = group.components[1]
        self.assertEqual(rider.damage_type, "穿刺")
        self.assertEqual(rider.scope, ApplicationScope.ONCE_SELECTABLE)

    def test_invalid_power_index_is_rejected(self):
        entry = default_entry()
        entry.update(target_id="target", count="2", power_indices="3")
        with self.assertRaises(ValueError):
            self.app_without_tk()._attack_group(entry)

    def test_advanced_entry_supports_manual_hits(self):
        entry = default_entry()
        entry.update(
            target_id="target",
            count="4",
            manual_hits=True,
            manual_hit_count="3",
            manual_critical_count="1",
        )
        group = self.app_without_tk()._attack_group(entry)
        self.assertEqual(group.manual_hit_count, 3)
        self.assertEqual(group.manual_critical_count, 1)
        group.validate()

    def test_old_entry_gets_manual_hit_defaults_without_losing_data(self):
        old = {"id": "old-entry", "name": "旧攻击", "attack_bonus": "8"}
        normalized = normalize_entry(old)
        self.assertEqual(normalized["id"], "old-entry")
        self.assertEqual(normalized["attack_bonus"], "8")
        self.assertFalse(normalized["manual_hits"])
        self.assertEqual(normalized["manual_critical_count"], "0")

    def test_advanced_modes_have_chinese_labels(self):
        self.assertEqual(MODE_LABELS["attack"], "攻击检定")
        self.assertEqual(MODE_LABELS["save"], "豁免检定")
        self.assertEqual(MODE_LABELS["auto"], "自动伤害")

    def test_entry_list_summary_uses_chinese_mode_and_target(self):
        target = default_target()
        entry = default_entry()
        entry.update(target_id=target["id"], mode="save", all_targets=True)
        self.assertEqual(entry_display_values(entry, [target]), (entry["name"], "豁免检定", "全部目标"))

    def test_quick_import_appends_without_overwriting(self):
        app = self.app_without_tk()
        old_target = default_target()
        old_entry = default_entry()
        old_entry["target_id"] = old_target["id"]
        app.targets = [old_target]
        app.entries = [old_entry]
        app._refresh_targets = lambda *_args: None
        app._refresh_entries = lambda *_args: None
        app._load_target = lambda *_args: None
        app._load_entry = lambda *_args: None
        app.show_advanced = lambda: None
        app._mark_stale = lambda: None
        app.status_var = type("Status", (), {"set": lambda self, value: None})()
        request = QuickAttackRequest(
            target_ac=18,
            attack_bonus=7,
            attack_count=2,
            roll_mode=RollMode.ADVANTAGE,
            damage_dice_count=2,
            damage_die_sides=6,
            damage_bonus=4,
        )
        app.import_quick_to_advanced(request)
        self.assertEqual((len(app.targets), len(app.entries)), (2, 2))
        self.assertIs(app.targets[0], old_target)
        self.assertIs(app.entries[0], old_entry)
        self.assertEqual(app.targets[1]["ac"], "18")
        self.assertEqual(app.entries[1]["advantage"], "1")


if __name__ == "__main__":
    unittest.main()
