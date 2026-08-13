from __future__ import annotations

import unittest
from dataclasses import replace

from dnd_calculator.engine import RulesEngine, RulesError
from dnd_calculator.models import (
    ApplicationScope,
    AttackGroup,
    AutoEffect,
    CritBehavior,
    DamageComponent,
    DamageReduction,
    DiceModifier,
    DiceTerm,
    RerollPolicy,
    ResolutionMode,
    SaveEffect,
    SaveOutcome,
    SelectableAttackModifier,
    Target,
)
from dnd_calculator.presets import apply_attack_preset, divine_smite, sneak_attack


class SequenceRng:
    def __init__(self, values):
        self.values = iter(values)

    def randint(self, low, high):
        value = next(self.values)
        if not low <= value <= high:
            raise AssertionError(f"测试骰值 {value} 不在 {low}..{high}")
        return value


def weapon(component_id="weapon", *, dice=None, damage_type="挥砍", **kwargs):
    dice = dice or DiceTerm(1, 8)
    return DamageComponent(
        component_id,
        "武器",
        dice,
        damage_type=damage_type,
        weapon_die=True,
        **kwargs,
    )


class AttackTests(unittest.TestCase):
    def setUp(self):
        self.target = Target("t", "目标", ac=15)

    def test_natural_one_always_misses_and_never_crits(self):
        group = AttackGroup("g", "攻击", "t", attack_bonus=99, crit_range=2)
        result = RulesEngine(SequenceRng([1])).resolve_attacks([group], [self.target])
        attack = result.attack_results[0]
        self.assertFalse(attack.hit)
        self.assertFalse(attack.critical)

    def test_expanded_critical_auto_hits(self):
        group = AttackGroup("g", "攻击", "t", attack_bonus=-20, crit_range=19)
        attack = RulesEngine(SequenceRng([19])).resolve_attacks([group], [self.target]).attack_results[0]
        self.assertTrue(attack.hit)
        self.assertTrue(attack.critical)

    def test_advantage_disadvantage_cancel(self):
        group = AttackGroup("g", "攻击", "t", advantage_sources=2, disadvantage_sources=1)
        attack = RulesEngine(SequenceRng([12])).resolve_attacks([group], [self.target]).attack_results[0]
        self.assertEqual(len(attack.d20_rolls), 1)

    def test_elven_accuracy_rolls_three_and_keeps_highest(self):
        group = AttackGroup("g", "攻击", "t", advantage_sources=1, elven_accuracy=True)
        attack = RulesEngine(SequenceRng([3, 18, 7])).resolve_attacks([group], [self.target]).attack_results[0]
        self.assertEqual(attack.selected_d20, 18)
        self.assertEqual(len(attack.d20_rolls), 3)

    def test_halfling_lucky_rerolls_only_one_natural_one(self):
        group = AttackGroup("g", "攻击", "t", advantage_sources=1, halfling_lucky=True)
        attack = RulesEngine(SequenceRng([1, 1, 14])).resolve_attacks([group], [self.target]).attack_results[0]
        self.assertEqual([(r.value, r.rerolled) for r in attack.d20_rolls], [(14, True), (1, False)])

    def test_signed_attack_dice_and_negative_format(self):
        group = AttackGroup(
            "g",
            "攻击",
            "t",
            attack_bonus=-2,
            attack_dice=(DiceModifier("灾祸术", DiceTerm(1, 4, -1)),),
        )
        attack = RulesEngine(SequenceRng([18, 3])).resolve_attacks([group], [self.target]).attack_results[0]
        self.assertEqual(attack.total, 13)
        self.assertIn("-2", attack.explanation)
        self.assertNotIn("+-", attack.explanation)

    def test_selectable_attack_modifier_can_rescue_one_miss(self):
        modifier = SelectableAttackModifier("bond", "勇气联结", DiceTerm(1, 4))
        group = AttackGroup("g", "攻击", "t", count=2, attack_bonus=2, selectable_attack_modifiers=(modifier,))
        engine = RulesEngine(SequenceRng([10, 12, 4]))
        session = engine.resolve_attacks([group], [self.target])
        self.assertFalse(session.attack_modifiers_resolved)
        self.assertFalse(session.attack_results[0].hit)
        resolved = engine.resolve_attack_modifiers(session, {"bond": "g:0"})
        self.assertTrue(resolved.attack_results[0].hit)
        self.assertTrue(resolved.attack_modifiers_resolved)
        self.assertFalse(resolved.attack_results[1].hit)

    def test_selectable_modifier_cannot_override_natural_one_or_change_critical(self):
        modifier = SelectableAttackModifier("m", "修正", DiceTerm(1, 20))
        group = AttackGroup("g", "攻击", "t", count=2, crit_range=19, selectable_attack_modifiers=(modifier,))
        engine = RulesEngine(SequenceRng([1, 19, 20, 2]))
        session = engine.resolve_attacks([group], [self.target])
        first = engine.resolve_attack_modifiers(session, {"m": "g:0"})
        self.assertFalse(first.attack_results[0].hit)
        self.assertFalse(first.attack_results[0].critical)
        with self.assertRaisesRegex(RulesError, "已经结算"):
            engine.resolve_attack_modifiers(first, {})

    def test_selectable_modifier_rejects_cross_group_attack(self):
        modifier = SelectableAttackModifier("m", "修正", DiceTerm(1, 4))
        groups = [AttackGroup("a", "甲", "t", selectable_attack_modifiers=(modifier,)), AttackGroup("b", "乙", "t")]
        session = RulesEngine(SequenceRng([10, 10])).resolve_attacks(groups, [self.target])
        with self.assertRaisesRegex(RulesError, "所属攻击组"):
            RulesEngine(SequenceRng([])).resolve_attack_modifiers(session, {"m": "b:0"})

    def test_groups_keep_independent_critical_results(self):
        groups = [
            AttackGroup("action", "动作", "t"),
            AttackGroup("bonus", "附赠动作", "t"),
        ]
        session = RulesEngine(SequenceRng([20, 10])).resolve_attacks(groups, [self.target])
        self.assertTrue(session.attack_results[0].critical)
        self.assertFalse(session.attack_results[1].critical)


class DamageTests(unittest.TestCase):
    def test_critical_doubles_dice_but_not_flat_bonus(self):
        target = Target("t", "目标", ac=10)
        component = weapon(flat_bonus=3)
        group = AttackGroup("g", "攻击", "t", components=(component,))
        engine = RulesEngine(SequenceRng([20, 4, 5]))
        damaged = engine.resolve_damage(engine.resolve_attacks([group], [target]))
        self.assertEqual(damaged.damage_results[0].total, 12)
        self.assertEqual(len(damaged.damage_results[0].components[0].dice), 2)

    def test_critical_immunity_cancels_extra_dice_only(self):
        target = Target("t", "目标", ac=10, crit_immune=True)
        group = AttackGroup("g", "攻击", "t", components=(weapon(flat_bonus=3),))
        engine = RulesEngine(SequenceRng([20, 4]))
        damaged = engine.resolve_damage(engine.resolve_attacks([group], [target]))
        self.assertTrue(damaged.attack_results[0].critical)
        self.assertFalse(damaged.damage_results[0].critical)
        self.assertEqual(damaged.damage_results[0].total, 7)

    def test_once_selectable_rider_only_on_chosen_hit(self):
        target = Target("t", "目标", ac=10)
        group = AttackGroup(
            "g", "攻击", "t", count=2, components=(weapon(), sneak_attack(2))
        )
        engine = RulesEngine(SequenceRng([15, 16, 3, 4, 5, 6]))
        session = engine.resolve_attacks([group], [target])
        damaged = engine.resolve_damage(session, {"sneak-attack": ["g:1"]})
        self.assertEqual(len(damaged.damage_results[0].components), 1)
        self.assertEqual(len(damaged.damage_results[1].components), 2)

    def test_once_selectable_rider_rejects_two_hits(self):
        target = Target("t", "目标", ac=10)
        group = AttackGroup("g", "攻击", "t", count=2, components=(weapon(), sneak_attack()))
        engine = RulesEngine(SequenceRng([15, 16]))
        session = engine.resolve_attacks([group], [target])
        with self.assertRaises(RulesError):
            engine.resolve_damage(session, {"sneak-attack": ["g:0", "g:1"]})

    def test_selectable_damage_rejects_cross_group_attack(self):
        target = Target("t", "目标", ac=10)
        groups = (
            AttackGroup("a", "甲", "t", components=(weapon("a-weapon"), sneak_attack())),
            AttackGroup("b", "乙", "t", components=(weapon("b-weapon"),)),
        )
        engine = RulesEngine(SequenceRng([15, 15]))
        session = engine.resolve_attacks(groups, [target])
        with self.assertRaisesRegex(RulesError, "所属攻击组"):
            engine.resolve_damage(session, {"sneak-attack": ["b:0"]})

    def test_all_damage_scopes_and_critical_behaviors_can_coexist(self):
        target = Target("t", "目标", ac=10)
        components = (
            weapon("base", dice=DiceTerm(1, 8), flat_bonus=3),
            DamageComponent("once", "选择一次", DiceTerm(1, 4), scope=ApplicationScope.ONCE_SELECTABLE),
            DamageComponent("many", "选择多个", DiceTerm(1, 6), scope=ApplicationScope.SELECTED_HITS),
            DamageComponent("crit", "仅重击", DiceTerm(1, 10), flat_bonus=2, scope=ApplicationScope.CRIT_ONLY, crit_behavior=CritBehavior.NORMAL),
        )
        group = AttackGroup("g", "攻击", "t", count=2, components=components)
        engine = RulesEngine(SequenceRng([20, 15, 4, 5, 2, 3, 7, 6, 4, 4]))
        session = engine.resolve_attacks([group], [target])
        damaged = engine.resolve_damage(session, {"once": ["g:1"], "many": ["g:0", "g:1"]})
        first, second = damaged.damage_results
        self.assertEqual([item.component_id for item in first.components], ["base", "many", "crit"])
        self.assertEqual([item.component_id for item in second.components], ["base", "once", "many"])
        self.assertEqual(first.total, 26)
        self.assertEqual(second.total, 17)

    def test_power_attack_is_snapshotted_per_attack_and_added_once(self):
        target = Target("t", "目标", ac=10)
        group = AttackGroup(
            "g",
            "攻击",
            "t",
            count=2,
            attack_bonus=5,
            power_attack_indices=frozenset({0}),
            components=(weapon("w1"), weapon("w2", damage_type="火焰")),
        )
        engine = RulesEngine(SequenceRng([15, 15, 2, 3, 4, 5]))
        session = engine.resolve_attacks([group], [target])
        damaged = engine.resolve_damage(session)
        self.assertTrue(damaged.attack_results[0].power_attack)
        self.assertFalse(damaged.attack_results[1].power_attack)
        self.assertEqual(damaged.damage_results[0].total, 15)
        self.assertEqual(damaged.damage_results[1].total, 9)

    def test_great_weapon_rerolls_eligible_weapon_die_once(self):
        target = Target("t", "目标", ac=10)
        component = weapon(reroll=RerollPolicy((1, 2), once=True, weapon_only=True))
        group = AttackGroup("g", "攻击", "t", components=(component,))
        engine = RulesEngine(SequenceRng([15, 1, 2]))
        damaged = engine.resolve_damage(engine.resolve_attacks([group], [target]))
        die = damaged.damage_results[0].components[0].dice[0]
        self.assertEqual((die.original, die.value, die.rerolled), (1, 2, True))
        self.assertEqual(damaged.damage_results[0].total, 2)

    def test_manual_reroll_recomputes_target_modifiers(self):
        target = Target("t", "目标", ac=10, resistances=frozenset({"火焰"}))
        group = AttackGroup("g", "攻击", "t", components=(weapon(damage_type="火焰"),))
        engine = RulesEngine(SequenceRng([15, 7, 3]))
        damaged = engine.resolve_damage(engine.resolve_attacks([group], [target]))
        rerolled = engine.reroll_selected(damaged, [("g:0", "weapon", 0)])
        die = rerolled.damage_results[0].components[0].dice[0]
        self.assertEqual((die.original, die.value), (7, 3))
        self.assertEqual(rerolled.damage_results[0].total, 1)

    def test_resistance_vulnerability_cancel_and_immunity_wins(self):
        base = Target(
            "t",
            "目标",
            ac=10,
            resistances=frozenset({"火焰"}),
            vulnerabilities=frozenset({"火焰"}),
        )
        group = AttackGroup("g", "攻击", "t", components=(weapon(damage_type="火焰"),))
        engine = RulesEngine(SequenceRng([15, 7]))
        damage = engine.resolve_damage(engine.resolve_attacks([group], [base])).damage_results[0]
        self.assertEqual(damage.total, 7)
        self.assertIn("抵消", damage.by_type[0].note)

        immune = replace(base, immunities=frozenset({"火焰"}))
        engine = RulesEngine(SequenceRng([15, 7]))
        damage = engine.resolve_damage(engine.resolve_attacks([group], [immune])).damage_results[0]
        self.assertEqual(damage.total, 0)

    def test_nonmagical_resistance_does_not_affect_magical_damage(self):
        target = Target("t", "目标", ac=10, nonmagical_resistances=frozenset({"挥砍"}))
        components = (weapon("normal"), replace(weapon("magic"), magical=True))
        group = AttackGroup("g", "攻击", "t", components=components)
        engine = RulesEngine(SequenceRng([15, 5, 5]))
        damage = engine.resolve_damage(engine.resolve_attacks([group], [target])).damage_results[0]
        self.assertEqual(damage.total, 7)

    def test_fixed_reduction_applies_once_per_damage_instance(self):
        target = Target(
            "t",
            "目标",
            ac=10,
            reductions=(DamageReduction(3, ("挥砍",), True),),
        )
        group = AttackGroup("g", "攻击", "t", components=(weapon(),))
        engine = RulesEngine(SequenceRng([15, 8]))
        damage = engine.resolve_damage(engine.resolve_attacks([group], [target])).damage_results[0]
        self.assertEqual(damage.total, 5)


class SaveAndAutoTests(unittest.TestCase):
    def test_save_has_no_automatic_one_or_twenty_rule(self):
        targets = (
            Target("a", "甲", saves=(("敏捷", 20),)),
            Target("b", "乙", saves=(("敏捷", -20),)),
        )
        effect = SaveEffect(
            "fire",
            "火焰效果",
            ("a", "b"),
            15,
            "敏捷",
            SaveOutcome.HALF,
            (DamageComponent("fire", "火焰", DiceTerm(1, 6), damage_type="火焰"),),
        )
        session = RulesEngine(SequenceRng([1, 20])).resolve_saves(effect, targets)
        self.assertTrue(session.save_results[0].succeeded)
        self.assertFalse(session.save_results[1].succeeded)

    def test_multi_target_save_rolls_damage_once_and_applies_defenses_independently(self):
        targets = (
            Target("a", "甲", saves=(("敏捷", 10),), resistances=frozenset({"火焰"})),
            Target("b", "乙", saves=(("敏捷", 0),), vulnerabilities=frozenset({"火焰"})),
        )
        effect = SaveEffect(
            "fireball",
            "火球术",
            ("a", "b"),
            15,
            "敏捷",
            SaveOutcome.HALF,
            (DamageComponent("fire", "火焰", DiceTerm(2, 6), damage_type="火焰"),),
        )
        engine = RulesEngine(SequenceRng([10, 10, 5, 5]))
        session = engine.resolve_damage(engine.resolve_saves(effect, targets))
        self.assertEqual([d.total for d in session.damage_results], [2, 20])
        self.assertEqual(
            session.damage_results[0].components[0].dice,
            session.damage_results[1].components[0].dice,
        )

    def test_auto_damage_supports_multiple_targets(self):
        targets = (Target("a", "甲"), Target("b", "乙"))
        effect = AutoEffect(
            "missile",
            "魔法飞弹",
            ("a", "b"),
            (DamageComponent("force", "飞弹", DiceTerm(1, 4), 1, "力场"),),
        )
        engine = RulesEngine(SequenceRng([3]))
        session = engine.resolve_damage(engine.resolve_auto(effect, targets))
        self.assertEqual(session.mode, ResolutionMode.AUTO)
        self.assertEqual([result.total for result in session.damage_results], [4, 4])


class PresetTests(unittest.TestCase):
    def test_presets_fix_documented_critical_ranges(self):
        group = AttackGroup("g", "攻击", "t")
        self.assertEqual(apply_attack_preset(group, "咒剑诅咒 19–20").crit_range, 19)
        self.assertEqual(apply_attack_preset(group, "勇士卓越重击 18–20").crit_range, 18)

    def test_smite_is_selectable_and_critical_eligible(self):
        component = divine_smite(2)
        self.assertEqual(component.scope, ApplicationScope.SELECTED_HITS)
        self.assertEqual(component.crit_behavior, CritBehavior.DOUBLE_DICE)


if __name__ == "__main__":
    unittest.main()
