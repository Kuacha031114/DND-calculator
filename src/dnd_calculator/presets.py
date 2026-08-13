"""常用 2014 规则预设；预设只填充通用字段，不校验角色资源。"""

from __future__ import annotations

from dataclasses import replace

from .models import (
    ApplicationScope,
    AttackGroup,
    CritBehavior,
    DamageComponent,
    DiceModifier,
    DiceTerm,
    RerollPolicy,
    SaveOutcome,
)

PRESET_NAMES = (
    "无",
    "神射手 -5/+10",
    "巨武器大师 -5/+10",
    "重武器战斗风格",
    "精灵精准",
    "半身人幸运",
    "咒剑诅咒 19–20",
    "勇士精通重击 19–20",
    "勇士卓越重击 18–20",
)


def apply_attack_preset(group: AttackGroup, name: str) -> AttackGroup:
    if name in ("神射手 -5/+10", "巨武器大师 -5/+10"):
        return replace(group, power_attack_indices=frozenset(range(group.count)))
    if name == "祝福术 +1d4":
        return replace(
            group,
            attack_dice=group.attack_dice + (DiceModifier("祝福术", DiceTerm(1, 4, 1)),),
        )
    if name == "灾祸术 -1d4":
        return replace(
            group,
            attack_dice=group.attack_dice + (DiceModifier("灾祸术", DiceTerm(1, 4, -1)),),
        )
    if name == "精灵精准":
        return replace(group, elven_accuracy=True, advantage_sources=max(1, group.advantage_sources))
    if name == "半身人幸运":
        return replace(group, halfling_lucky=True)
    if name in ("咒剑诅咒 19–20", "勇士精通重击 19–20"):
        return replace(group, crit_range=19)
    if name == "勇士卓越重击 18–20":
        return replace(group, crit_range=18)
    if name == "重武器战斗风格":
        components = tuple(
            replace(
                component,
                reroll=RerollPolicy(faces=(1, 2), once=True, weapon_only=True),
            )
            if component.weapon_die
            else component
            for component in group.components
        )
        return replace(group, components=components)
    return group


def sneak_attack(dice_count: int = 1, sides: int = 6) -> DamageComponent:
    return DamageComponent(
        "sneak-attack",
        "偷袭",
        DiceTerm(dice_count, sides),
        damage_type="自定义",
        scope=ApplicationScope.ONCE_SELECTABLE,
        crit_behavior=CritBehavior.DOUBLE_DICE,
    )


def divine_smite(dice_count: int = 2, sides: int = 8) -> DamageComponent:
    return DamageComponent(
        "divine-smite",
        "至圣斩",
        DiceTerm(dice_count, sides),
        damage_type="光耀",
        scope=ApplicationScope.SELECTED_HITS,
        crit_behavior=CritBehavior.DOUBLE_DICE,
    )


def savage_attacks(sides: int = 8) -> DamageComponent:
    return DamageComponent(
        "savage-attacks",
        "凶蛮攻击额外武器骰",
        DiceTerm(1, sides),
        damage_type="自定义",
        weapon_die=True,
        scope=ApplicationScope.CRIT_ONLY,
        crit_behavior=CritBehavior.NORMAL,
    )


def brutal_critical(extra_dice: int = 1, sides: int = 8) -> DamageComponent:
    return DamageComponent(
        "brutal-critical",
        "野蛮重击额外武器骰",
        DiceTerm(extra_dice, sides),
        damage_type="自定义",
        weapon_die=True,
        scope=ApplicationScope.CRIT_ONLY,
        crit_behavior=CritBehavior.NORMAL,
    )


SAVE_PRESETS = {
    "成功半伤": SaveOutcome.HALF,
    "成功无伤": SaveOutcome.NONE,
    "成功全伤": SaveOutcome.FULL,
}
