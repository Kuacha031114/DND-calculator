import unittest

from dnd_calculator.models import RollMode
from dnd_calculator.quick import QuickAttackRequest, resolve_quick_attack
from test_engine import SequenceRng
from dnd_calculator.engine import RulesEngine


class QuickAttackTests(unittest.TestCase):
    def test_one_click_resolves_attack_and_damage(self):
        summary = resolve_quick_attack(
            QuickAttackRequest(), RulesEngine(SequenceRng([15, 6]))
        )
        self.assertEqual((summary.hit_count, summary.total_damage), (1, 9))
        self.assertTrue(summary.session.damage_results)

    def test_miss_has_zero_damage(self):
        summary = resolve_quick_attack(
            QuickAttackRequest(), RulesEngine(SequenceRng([2]))
        )
        self.assertEqual((summary.hit_count, summary.total_damage), (0, 0))

    def test_critical_doubles_dice(self):
        summary = resolve_quick_attack(
            QuickAttackRequest(), RulesEngine(SequenceRng([20, 4, 5]))
        )
        self.assertEqual((summary.critical_count, summary.total_damage), (1, 12))

    def test_advantage_uses_two_d20(self):
        request = QuickAttackRequest(roll_mode=RollMode.ADVANTAGE)
        summary = resolve_quick_attack(request, RulesEngine(SequenceRng([3, 18, 4])))
        self.assertEqual(summary.session.attack_results[0].selected_d20, 18)

    def test_disadvantage_uses_lower_d20(self):
        request = QuickAttackRequest(target_ac=10, roll_mode=RollMode.DISADVANTAGE)
        summary = resolve_quick_attack(request, RulesEngine(SequenceRng([18, 4])))
        self.assertEqual((summary.hit_count, summary.total_damage), (0, 0))

    def test_multiple_attacks_and_power_attack(self):
        request = QuickAttackRequest(
            target_ac=10,
            attack_count=2,
            attack_bonus=10,
            power_attack=True,
        )
        summary = resolve_quick_attack(
            request, RulesEngine(SequenceRng([10, 12, 3, 4]))
        )
        self.assertEqual(summary.hit_count, 2)
        self.assertEqual(summary.total_damage, 33)
        self.assertTrue(all(item.power_attack for item in summary.session.attack_results))

    def test_expanded_critical_range(self):
        request = QuickAttackRequest(target_ac=99, crit_range=19)
        summary = resolve_quick_attack(
            request, RulesEngine(SequenceRng([19, 2, 3]))
        )
        self.assertEqual(summary.critical_count, 1)

    def test_validation_is_field_specific(self):
        with self.assertRaisesRegex(ValueError, "目标 AC"):
            resolve_quick_attack(QuickAttackRequest(target_ac=0))

    def test_manual_hits_skip_ac_and_d20(self):
        request = QuickAttackRequest(
            target_ac=0,
            attack_count=3,
            manual_hit_count=2,
            manual_critical_count=1,
        )
        summary = resolve_quick_attack(
            request, RulesEngine(SequenceRng([4, 5, 6]))
        )
        self.assertEqual((summary.hit_count, summary.critical_count), (2, 1))
        self.assertEqual(summary.total_damage, 21)
        self.assertTrue(all(not attack.d20_rolls for attack in summary.session.attack_results))
        self.assertIn("未使用 AC", summary.session.attack_results[0].explanation)

    def test_manual_critical_count_cannot_exceed_hits(self):
        with self.assertRaisesRegex(ValueError, "重击次数"):
            resolve_quick_attack(
                QuickAttackRequest(
                    attack_count=2,
                    manual_hit_count=1,
                    manual_critical_count=2,
                )
            )

    def test_manual_hits_keep_damage_bonuses_and_power_attack_damage(self):
        summary = resolve_quick_attack(
            QuickAttackRequest(
                attack_count=1,
                power_attack=True,
                damage_dice_count=0,
                damage_bonus=3,
                manual_hit_count=1,
            ),
            RulesEngine(SequenceRng([])),
        )
        self.assertEqual(summary.total_damage, 13)
        self.assertTrue(summary.session.attack_results[0].power_attack)


if __name__ == "__main__":
    unittest.main()
