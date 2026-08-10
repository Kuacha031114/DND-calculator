"""桌面与网页共用的配置规范化和规则模型适配层。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Mapping, Sequence
from uuid import uuid4

from .config import CONFIG_VERSION
from .models import (
    STANDARD_ABILITIES,
    AttackGroup,
    DamageComponent,
    DamageReduction,
    DiceModifier,
    DiceTerm,
    RerollPolicy,
    ResolutionMode,
    Target,
)
from .presets import (
    apply_attack_preset,
    brutal_critical,
    divine_smite,
    savage_attacks,
    sneak_attack,
)


MODE_LABELS = {
    ResolutionMode.ATTACK.value: "攻击检定",
    ResolutionMode.SAVE.value: "豁免检定",
    ResolutionMode.AUTO.value: "自动伤害",
}

QUICK_DEFAULTS: dict[str, object] = {
    "target_ac": "15",
    "attack_bonus": "5",
    "attack_count": "1",
    "roll_mode": "普通",
    "crit_range": "20",
    "power_attack": False,
    "damage_dice_count": "1",
    "damage_die_sides": "8",
    "damage_bonus": "3",
    "manual_hits": False,
    "manual_hit_count": "1",
    "manual_critical_count": "0",
}


def identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_target(index: int = 1) -> dict[str, Any]:
    return {
        "id": identifier("target"),
        "name": f"目标 {index}",
        "ac": "15",
        "saves": {ability: "0" for ability in STANDARD_ABILITIES},
        "resistances": "",
        "vulnerabilities": "",
        "immunities": "",
        "nonmagical_resistances": "",
        "crit_immune": False,
        "fixed_reduction": "0",
    }


def normalize_target(target: Mapping[str, Any], index: int = 1) -> dict[str, Any]:
    normalized = {**default_target(index), **dict(target)}
    normalized["saves"] = {
        **{ability: "0" for ability in STANDARD_ABILITIES},
        **dict(target.get("saves") or {}),
    }
    return normalized


def default_entry(index: int = 1) -> dict[str, Any]:
    return {
        "id": identifier("entry"),
        "name": f"攻击 {index}",
        "mode": ResolutionMode.ATTACK.value,
        "target_id": "",
        "all_targets": False,
        "count": "1",
        "attack_bonus": "5",
        "manual_hits": False,
        "manual_hit_count": "1",
        "manual_critical_count": "0",
        "dc": "15",
        "save_ability": "敏捷",
        "save_outcome": "成功半伤",
        "damage_name": "武器",
        "dice_count": "1",
        "dice_sides": "8",
        "flat_bonus": "3",
        "damage_type": "挥砍",
        "advantage": "0",
        "disadvantage": "0",
        "crit_range": "20",
        "elven_accuracy": False,
        "halfling_lucky": False,
        "power_attack": False,
        "power_indices": "",
        "weapon_die": True,
        "magical": False,
        "great_weapon_fighting": False,
        "bless": False,
        "bane": False,
        "preset": "无",
        "rider": "无",
        "rider_dice": "1",
        "rider_sides": "6",
    }


def normalize_entry(entry: Mapping[str, Any], index: int = 1) -> dict[str, Any]:
    """为旧 v3 条目补齐新增的可选字段，并保留原数据。"""
    return {**default_entry(index), **dict(entry)}


def default_config() -> dict[str, Any]:
    target = default_target()
    entry = default_entry()
    entry["target_id"] = target["id"]
    return {
        "config_version": CONFIG_VERSION,
        "quick": dict(QUICK_DEFAULTS),
        "targets": [target],
        "entries": [entry],
        "custom_presets": {},
        "onboarding_seen": False,
        "help_expanded": False,
        "web": {"active_view": "quick"},
    }


def normalize_config(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """规范化桌面或网页配置；未知字段原样保留以便双向迁移。"""
    if data is None:
        return default_config()
    if not isinstance(data, Mapping):
        raise ValueError("配置根节点必须是对象")
    version = data.get("config_version", CONFIG_VERSION)
    if version != CONFIG_VERSION:
        raise ValueError(f"不支持配置版本 {version}，当前仅支持版本 {CONFIG_VERSION}")

    normalized = deepcopy(dict(data))
    raw_targets = data.get("targets") or []
    targets = [normalize_target(item, index + 1) for index, item in enumerate(raw_targets)]
    if not targets:
        targets = [default_target()]
    raw_entries = data.get("entries") or []
    entries = [normalize_entry(item, index + 1) for index, item in enumerate(raw_entries)]
    if not entries:
        entries = [default_entry()]
    target_ids = {target["id"] for target in targets}
    fallback_target = targets[0]["id"]
    for entry in entries:
        if entry.get("target_id") not in target_ids:
            entry["target_id"] = fallback_target

    normalized.update(
        config_version=CONFIG_VERSION,
        quick={**QUICK_DEFAULTS, **dict(data.get("quick") or {})},
        targets=targets,
        entries=entries,
        custom_presets=deepcopy(dict(data.get("custom_presets") or {})),
        web={"active_view": "quick", **dict(data.get("web") or {})},
    )
    return normalized


def entry_display_values(
    entry: Mapping[str, Any], targets: Sequence[Mapping[str, Any]]
) -> tuple[str, str, str]:
    target = next((item for item in targets if item["id"] == entry.get("target_id")), None)
    uses_all = entry.get("mode") in (ResolutionMode.SAVE.value, ResolutionMode.AUTO.value)
    target_name = "全部目标" if uses_all and entry.get("all_targets") else (
        target["name"] if target else "未指定"
    )
    mode = str(entry.get("mode", ""))
    return str(entry.get("name", "未命名条目")), MODE_LABELS.get(mode, mode), str(target_name)


def parse_damage_types(value: object) -> frozenset[str]:
    text = str(value or "")
    return frozenset(part.strip() for part in text.replace("，", ",").split(",") if part.strip())


def targets_from_config(items: Sequence[Mapping[str, Any]]) -> tuple[Target, ...]:
    targets = []
    for item in items:
        reduction = int(item.get("fixed_reduction", "0"))
        targets.append(
            Target(
                str(item["id"]),
                str(item.get("name") or "未命名目标"),
                int(item.get("ac", 15)),
                tuple(
                    (ability, int(dict(item.get("saves") or {}).get(ability, "0")))
                    for ability in STANDARD_ABILITIES
                ),
                parse_damage_types(item.get("resistances")),
                parse_damage_types(item.get("vulnerabilities")),
                parse_damage_types(item.get("immunities")),
                parse_damage_types(item.get("nonmagical_resistances")),
                bool(item.get("crit_immune", False)),
                (DamageReduction(reduction),) if reduction > 0 else (),
            )
        )
    return tuple(targets)


def component_from_entry(entry: Mapping[str, Any]) -> DamageComponent:
    policy = (
        RerollPolicy((1, 2), True, True)
        if entry.get("great_weapon_fighting")
        else RerollPolicy()
    )
    return DamageComponent(
        f"{entry['id']}:base",
        str(entry.get("damage_name") or "伤害"),
        DiceTerm(int(entry.get("dice_count", 1)), int(entry.get("dice_sides", 8))),
        int(entry.get("flat_bonus", 0)),
        str(entry.get("damage_type") or "挥砍"),
        bool(entry.get("weapon_die", True)),
        bool(entry.get("magical", False)),
        reroll=policy,
    )


def attack_group_from_entry(entry: Mapping[str, Any]) -> AttackGroup:
    component = component_from_entry(entry)
    components = [component]
    rider_count = int(entry.get("rider_dice", 1))
    rider_sides = int(entry.get("rider_sides", 6))
    rider_name = entry.get("rider", "无")
    common = {
        "damage_type": str(entry.get("damage_type") or "挥砍"),
        "magical": bool(entry.get("magical", False)),
    }
    if rider_name == "偷袭":
        components.append(replace(sneak_attack(rider_count, rider_sides), component_id=f"{entry['id']}:sneak", **common))
    elif rider_name == "至圣斩":
        components.append(replace(divine_smite(rider_count, rider_sides), component_id=f"{entry['id']}:smite"))
    elif rider_name == "凶蛮攻击":
        components.append(replace(savage_attacks(rider_sides), component_id=f"{entry['id']}:savage", **common))
    elif rider_name == "野蛮重击":
        components.append(replace(brutal_critical(rider_count, rider_sides), component_id=f"{entry['id']}:brutal", **common))

    modifiers = []
    if entry.get("bless"):
        modifiers.append(DiceModifier("祝福术", DiceTerm(1, 4, 1)))
    if entry.get("bane"):
        modifiers.append(DiceModifier("灾祸术", DiceTerm(1, 4, -1)))
    count = int(entry.get("count", 1))
    if entry.get("power_attack"):
        power_indices = frozenset(range(count))
    else:
        values = [part.strip() for part in str(entry.get("power_indices", "")).replace("，", ",").split(",") if part.strip()]
        power_indices = frozenset(int(value) - 1 for value in values)
        if any(index < 0 or index >= count for index in power_indices):
            raise ValueError("-5/+10 攻击序号必须在本组攻击次数范围内")

    group = AttackGroup(
        str(entry["id"]),
        str(entry.get("name") or "未命名攻击"),
        str(entry.get("target_id") or ""),
        count,
        int(entry.get("attack_bonus", 0)),
        int(entry.get("advantage", 0)),
        int(entry.get("disadvantage", 0)),
        bool(entry.get("elven_accuracy", False)),
        bool(entry.get("halfling_lucky", False)),
        int(entry.get("crit_range", 20)),
        tuple(modifiers),
        power_indices,
        components=tuple(components),
        manual_hit_count=int(entry.get("manual_hit_count", 0)) if entry.get("manual_hits") else None,
        manual_critical_count=int(entry.get("manual_critical_count", 0)) if entry.get("manual_hits") else 0,
    )
    return apply_attack_preset(group, str(entry.get("preset") or "无"))
