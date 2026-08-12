"""D&D 5e 2014 攻击、豁免与伤害纯规则引擎。"""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import replace

from .models import (
    ApplicationScope,
    AttackGroup,
    AttackResult,
    AutoEffect,
    ComponentRoll,
    CritBehavior,
    D20Roll,
    DamageComponent,
    DamageInstanceResult,
    DamageTypeResult,
    ResolutionMode,
    ResolutionSession,
    RolledDie,
    SaveEffect,
    SaveOutcome,
    SaveResult,
    Target,
)


class RulesError(ValueError):
    """输入违反结算约束。"""


class RulesEngine:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    def _d20(self, halfling_lucky: bool = False) -> D20Roll:
        original = self.rng.randint(1, 20)
        if halfling_lucky and original == 1:
            return D20Roll(original=original, value=self.rng.randint(1, 20), rerolled=True)
        return D20Roll(original=original, value=original)

    def _roll_attack_d20s(self, group: AttackGroup) -> tuple[D20Roll, ...]:
        has_advantage = group.advantage_sources > 0
        has_disadvantage = group.disadvantage_sources > 0
        if has_advantage and has_disadvantage:
            count = 1
        elif has_advantage:
            count = 3 if group.elven_accuracy else 2
        elif has_disadvantage:
            count = 2
        else:
            count = 1

        rolls = [self._d20(False) for _ in range(count)]
        if group.halfling_lucky:
            for index, roll in enumerate(rolls):
                if roll.value == 1:
                    rolls[index] = D20Roll(1, self.rng.randint(1, 20), True)
                    break
        return tuple(rolls)

    @staticmethod
    def _choose_d20(group: AttackGroup, rolls: Sequence[D20Roll]) -> int:
        values = [roll.value for roll in rolls]
        has_advantage = group.advantage_sources > 0
        has_disadvantage = group.disadvantage_sources > 0
        if has_advantage and has_disadvantage:
            return values[0]
        if has_advantage:
            return max(values)
        if has_disadvantage:
            return min(values)
        return values[0]

    def _roll_signed_dice(self, group: AttackGroup) -> tuple[int, str]:
        total = 0
        pieces = []
        for modifier in group.attack_dice:
            values = [self.rng.randint(1, modifier.dice.sides) for _ in range(modifier.dice.count)]
            subtotal = sum(values) * modifier.dice.sign
            total += subtotal
            sign = "+" if modifier.dice.sign > 0 else "-"
            pieces.append(f"{sign}{modifier.name}({','.join(map(str, values))})")
        return total, " ".join(pieces)

    def resolve_attacks(
        self, groups: Sequence[AttackGroup], targets: Sequence[Target]
    ) -> ResolutionSession:
        if not groups:
            raise RulesError("至少需要一个攻击条目")
        target_map = self._validate_targets(targets)
        results = []
        for group in groups:
            group.validate()
            if group.target_id not in target_map:
                raise RulesError(f"攻击组 {group.name} 引用了不存在的目标")
            if group.manual_hit_count is not None:
                results.extend(self._manual_attack_results(group))
                continue
            target = target_map[group.target_id]
            for index in range(group.count):
                rolls = self._roll_attack_d20s(group)
                selected = self._choose_d20(group, rolls)
                dice_total, dice_text = self._roll_signed_dice(group)
                use_power = index in group.power_attack_indices
                power_penalty = group.power_attack_penalty if use_power else 0
                total = selected + group.attack_bonus + dice_total + power_penalty

                if selected == 1:
                    hit, critical = False, False
                    verdict = "自然 1，自动未命中"
                elif selected >= group.crit_range:
                    hit, critical = True, True
                    verdict = f"自然 {selected}，重击并自动命中"
                else:
                    hit, critical = total >= target.ac, False
                    verdict = f"{'命中' if hit else '未命中'} AC {target.ac}"

                power_text = f" {group.power_attack_penalty:+d}" if use_power else ""
                modifier_text = f" {dice_text}" if dice_text else ""
                explanation = (
                    f"d20 {selected} {group.attack_bonus:+d}{power_text}{modifier_text} "
                    f"= {total}；{verdict}"
                )
                results.append(
                    AttackResult(
                        attack_id=f"{group.group_id}:{index}",
                        group_id=group.group_id,
                        group_name=group.name,
                        index=index,
                        target_id=group.target_id,
                        d20_rolls=rolls,
                        selected_d20=selected,
                        dice_modifier_total=dice_total,
                        total=total,
                        hit=hit,
                        critical=critical,
                        power_attack=use_power,
                        explanation=explanation,
                    )
                )
        return ResolutionSession(
            mode=ResolutionMode.ATTACK,
            targets=tuple(targets),
            attack_groups=tuple(groups),
            attack_results=tuple(results),
        )

    @staticmethod
    def _manual_attack_results(group: AttackGroup) -> list[AttackResult]:
        """为 AC 未知的场景生成手动命中快照。

        重击排在前，其后是普通命中和未命中，便于 UI 稳定地按攻击实例 ID
        选择偷袭、至圣斩等附加伤害。
        """
        assert group.manual_hit_count is not None
        results = []
        for index in range(group.count):
            critical = index < group.manual_critical_count
            hit = index < group.manual_hit_count
            if critical:
                verdict = "手动指定重击"
            elif hit:
                verdict = "手动指定命中"
            else:
                verdict = "手动指定未命中"
            results.append(
                AttackResult(
                    attack_id=f"{group.group_id}:{index}",
                    group_id=group.group_id,
                    group_name=group.name,
                    index=index,
                    target_id=group.target_id,
                    d20_rolls=(),
                    selected_d20=0,
                    dice_modifier_total=0,
                    total=0,
                    hit=hit,
                    critical=critical,
                    power_attack=index in group.power_attack_indices,
                    explanation=f"{verdict}；未投 d20，未使用 AC 和命中加值",
                )
            )
        return results

    def resolve_saves(
        self, effect: SaveEffect, targets: Sequence[Target]
    ) -> ResolutionSession:
        effect.validate()
        target_map = self._validate_targets(targets)
        results = []
        for target_id in effect.target_ids:
            if target_id not in target_map:
                raise RulesError(f"豁免效果引用了不存在的目标 {target_id}")
            target = target_map[target_id]
            d20 = self.rng.randint(1, 20)
            bonus = target.save_bonus(effect.ability)
            total = d20 + bonus
            results.append(SaveResult(target_id, d20, bonus, total, total >= effect.dc))
        return ResolutionSession(
            mode=ResolutionMode.SAVE,
            targets=tuple(targets),
            save_effect=effect,
            save_results=tuple(results),
        )

    def resolve_auto(
        self, effect: AutoEffect, targets: Sequence[Target]
    ) -> ResolutionSession:
        effect.validate()
        target_map = self._validate_targets(targets)
        missing = [target_id for target_id in effect.target_ids if target_id not in target_map]
        if missing:
            raise RulesError(f"自动伤害引用了不存在的目标：{', '.join(missing)}")
        return ResolutionSession(
            mode=ResolutionMode.AUTO,
            targets=tuple(targets),
            auto_effect=effect,
        )

    def resolve_damage(
        self,
        session: ResolutionSession,
        rider_selections: Mapping[str, Iterable[str]] | None = None,
    ) -> ResolutionSession:
        selections = {key: tuple(value) for key, value in (rider_selections or {}).items()}
        if session.mode is ResolutionMode.ATTACK:
            results = self._resolve_attack_damage(session, selections)
        elif session.mode is ResolutionMode.SAVE:
            results = self._resolve_save_damage(session)
        elif session.mode is ResolutionMode.AUTO:
            results = self._resolve_auto_damage(session)
        else:
            raise RulesError("未知结算模式")
        frozen_selections = tuple(sorted((key, tuple(value)) for key, value in selections.items()))
        return replace(session, rider_selections=frozen_selections, damage_results=tuple(results))

    def reroll_selected(
        self,
        session: ResolutionSession,
        references: Iterable[tuple[str, str, int]],
    ) -> ResolutionSession:
        """手动重骰指定结果中的单颗骰子；规则型一次重骰由 RerollPolicy 处理。"""
        selected = set(references)
        available = {
            (result.source_id, component.component_id, index)
            for result in session.damage_results
            for component in result.components
            for index, _die in enumerate(component.dice)
        }
        missing = selected - available
        if missing:
            raise RulesError("重骰引用不存在或结算结果已经变化")
        targets = {target.target_id: target for target in session.targets}
        updated = []
        for result in session.damage_results:
            components = []
            for component in result.components:
                dice = []
                for index, die in enumerate(component.dice):
                    if (result.source_id, component.component_id, index) in selected:
                        dice.append(
                            RolledDie(
                                die.sides,
                                self.rng.randint(1, die.sides),
                                original=die.value,
                                rerolled=True,
                            )
                        )
                    else:
                        dice.append(die)
                raw = sum(die.value for die in dice) + component.flat_bonus
                components.append(replace(component, dice=tuple(dice), raw_total=max(0, raw)))
            outcome = self._outcome_for_damage_result(session, result)
            updated.append(
                self._build_damage_result(
                    result.source_id,
                    targets[result.target_id],
                    result.critical,
                    tuple(components),
                    outcome,
                )
            )
        return replace(session, damage_results=tuple(updated))

    @staticmethod
    def _outcome_for_damage_result(
        session: ResolutionSession, result: DamageInstanceResult
    ) -> SaveOutcome:
        if session.mode is not ResolutionMode.SAVE:
            return SaveOutcome.FULL
        assert session.save_effect is not None
        save = next(item for item in session.save_results if item.target_id == result.target_id)
        return session.save_effect.success_outcome if save.succeeded else SaveOutcome.FULL

    def _resolve_attack_damage(
        self, session: ResolutionSession, selections: Mapping[str, tuple[str, ...]]
    ) -> list[DamageInstanceResult]:
        groups = {group.group_id: group for group in session.attack_groups}
        targets = {target.target_id: target for target in session.targets}
        hit_ids = {result.attack_id for result in session.attack_results if result.hit}
        self._validate_rider_selections(groups.values(), selections, hit_ids)
        output = []
        for attack in session.attack_results:
            if not attack.hit:
                continue
            group = groups[attack.group_id]
            target = targets[attack.target_id]
            effective_critical = attack.critical and not target.crit_immune
            rolls = []
            power_damage_applied = False
            for component in group.components:
                if not self._component_applies(component, attack, selections, effective_critical):
                    continue
                extra_flat = 0
                if attack.power_attack and component.weapon_die and not power_damage_applied:
                    extra_flat = group.power_attack_damage
                    power_damage_applied = True
                rolls.append(self._roll_component(component, effective_critical, extra_flat))
            if attack.power_attack and not power_damage_applied:
                rolls.append(
                    ComponentRoll(
                        component_id="power-attack",
                        name="-5/+10 额外伤害",
                        damage_type="自定义",
                        magical=False,
                        dice=(),
                        flat_bonus=group.power_attack_damage,
                        raw_total=group.power_attack_damage,
                    )
                )
            output.append(
                self._build_damage_result(
                    attack.attack_id, target, effective_critical, tuple(rolls), SaveOutcome.FULL
                )
            )
        return output

    @staticmethod
    def _validate_rider_selections(
        groups: Iterable[AttackGroup],
        selections: Mapping[str, tuple[str, ...]],
        hit_ids: set[str],
    ) -> None:
        components = {
            component.component_id: component
            for group in groups
            for component in group.components
        }
        for component_id, attack_ids in selections.items():
            if component_id not in components:
                raise RulesError(f"选择了未知伤害组件 {component_id}")
            if any(attack_id not in hit_ids for attack_id in attack_ids):
                raise RulesError("附加伤害只能选择已命中的攻击")
            component = components[component_id]
            if component.scope is ApplicationScope.ONCE_SELECTABLE and len(set(attack_ids)) > 1:
                raise RulesError(f"{component.name} 每次结算最多选择一次")

    @staticmethod
    def _component_applies(
        component: DamageComponent,
        attack: AttackResult,
        selections: Mapping[str, tuple[str, ...]],
        effective_critical: bool,
    ) -> bool:
        if component.scope is ApplicationScope.EVERY_HIT:
            return True
        if component.scope is ApplicationScope.CRIT_ONLY:
            return effective_critical
        return attack.attack_id in selections.get(component.component_id, ())

    def _resolve_save_damage(self, session: ResolutionSession) -> list[DamageInstanceResult]:
        assert session.save_effect is not None
        effect = session.save_effect
        targets = {target.target_id: target for target in session.targets}
        shared_rolls = tuple(self._roll_component(component, False) for component in effect.components)
        output = []
        for save in session.save_results:
            outcome = effect.success_outcome if save.succeeded else SaveOutcome.FULL
            output.append(
                self._build_damage_result(
                    f"{effect.effect_id}:{save.target_id}",
                    targets[save.target_id],
                    False,
                    shared_rolls,
                    outcome,
                )
            )
        return output

    def _resolve_auto_damage(self, session: ResolutionSession) -> list[DamageInstanceResult]:
        assert session.auto_effect is not None
        effect = session.auto_effect
        targets = {target.target_id: target for target in session.targets}
        shared_rolls = tuple(self._roll_component(component, False) for component in effect.components)
        return [
            self._build_damage_result(
                f"{effect.effect_id}:{target_id}",
                targets[target_id],
                False,
                shared_rolls,
                SaveOutcome.FULL,
            )
            for target_id in effect.target_ids
        ]

    def _roll_component(
        self, component: DamageComponent, critical: bool, extra_flat: int = 0
    ) -> ComponentRoll:
        count = component.dice.count
        if critical and component.crit_behavior is CritBehavior.DOUBLE_DICE:
            count *= 2
        dice = []
        for _ in range(count):
            first = self.rng.randint(1, component.dice.sides)
            eligible = (
                first in component.reroll.faces
                and (not component.reroll.weapon_only or component.weapon_die)
            )
            if eligible:
                dice.append(
                    RolledDie(
                        sides=component.dice.sides,
                        original=first,
                        value=self.rng.randint(1, component.dice.sides),
                        rerolled=True,
                    )
                )
            else:
                dice.append(RolledDie(component.dice.sides, first))
        flat = component.flat_bonus + extra_flat
        raw = sum(die.value for die in dice) * component.dice.sign + flat
        return ComponentRoll(
            component.component_id,
            component.name,
            component.damage_type,
            component.magical,
            tuple(dice),
            flat,
            raw,
        )

    def _build_damage_result(
        self,
        source_id: str,
        target: Target,
        critical: bool,
        components: tuple[ComponentRoll, ...],
        save_outcome: SaveOutcome,
    ) -> DamageInstanceResult:
        buckets: MutableMapping[tuple[str, bool], int] = {}
        for component in components:
            key = (component.damage_type, component.magical)
            buckets[key] = buckets.get(key, 0) + component.raw_total
        buckets = {key: max(0, value) for key, value in buckets.items()}

        reduced = dict(buckets)
        reduction_notes: dict[tuple[str, bool], list[str]] = {key: [] for key in buckets}
        for reduction in target.reductions:
            remaining = max(0, reduction.amount)
            for key in sorted(reduced):
                damage_type, magical = key
                matches_type = not reduction.damage_types or damage_type in reduction.damage_types
                matches_magic = not reduction.nonmagical_only or not magical
                if remaining and matches_type and matches_magic:
                    applied = min(remaining, reduced[key])
                    reduced[key] -= applied
                    remaining -= applied
                    if applied:
                        reduction_notes[key].append(f"固定减伤 {applied}")

        by_type = []
        for key in sorted(buckets):
            damage_type, magical = key
            raw = buckets[key]
            after_reduction = reduced[key]
            if save_outcome is SaveOutcome.NONE:
                after_save = 0
            elif save_outcome is SaveOutcome.HALF:
                after_save = after_reduction // 2
            else:
                after_save = after_reduction

            resisted = damage_type in target.resistances or (
                not magical and damage_type in target.nonmagical_resistances
            )
            vulnerable = damage_type in target.vulnerabilities
            immune = damage_type in target.immunities
            notes = reduction_notes[key]
            if save_outcome is SaveOutcome.HALF:
                notes.append("豁免成功半伤")
            elif save_outcome is SaveOutcome.NONE:
                notes.append("豁免成功无伤")
            if immune:
                final = 0
                notes.append("免疫")
            elif resisted and vulnerable:
                final = after_save
                notes.append("抗性与易伤抵消")
            elif resisted:
                final = after_save // 2
                notes.append("抗性")
            elif vulnerable:
                final = after_save * 2
                notes.append("易伤")
            else:
                final = after_save
            if magical:
                notes.append("魔法")
            by_type.append(
                DamageTypeResult(
                    damage_type,
                    raw,
                    after_reduction,
                    after_save,
                    final,
                    "、".join(notes),
                )
            )
        return DamageInstanceResult(
            source_id,
            target.target_id,
            critical,
            components,
            tuple(by_type),
            sum(item.final for item in by_type),
        )

    @staticmethod
    def _validate_targets(targets: Sequence[Target]) -> dict[str, Target]:
        if not targets:
            raise RulesError("至少需要一个目标")
        target_map = {}
        for target in targets:
            target.validate()
            if target.target_id in target_map:
                raise RulesError(f"目标 ID 重复：{target.target_id}")
            target_map[target.target_id] = target
        return target_map


def format_d20_rolls(rolls: Sequence[D20Roll]) -> str:
    def show(roll: D20Roll) -> str:
        return f"{roll.original}→{roll.value}" if roll.rerolled else str(roll.value)

    return "/".join(show(roll) for roll in rolls)
