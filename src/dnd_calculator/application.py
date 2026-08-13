"""桌面与网页共用的配置规范化和规则模型适配层。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any
from uuid import uuid4

from .analysis import default_analysis, normalize_analysis
from .config import CONFIG_VERSION
from .models import (
    STANDARD_ABILITIES,
    ApplicationScope,
    AttackGroup,
    CritBehavior,
    DamageComponent,
    DamageReduction,
    DiceModifier,
    DiceTerm,
    RerollPolicy,
    ResolutionMode,
    SelectableAttackModifier,
    Target,
)
from .presets import (
    apply_attack_preset,
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
    entry_id = identifier("entry")
    return {
        "id": entry_id,
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
        "attack_modifiers": [],
        "damage_components": [default_damage_component(f"{entry_id}:damage")],
        "advantage": "0",
        "disadvantage": "0",
        "crit_range": "20",
        "elven_accuracy": False,
        "halfling_lucky": False,
        "power_attack": False,
        "power_indices": "",
        "great_weapon_fighting": False,
        "preset": "无",
    }


def default_attack_modifier(prefix: str = "modifier") -> dict[str, Any]:
    return {
        "id": identifier(prefix), "name": "命中修正", "dice_count": "1",
        "dice_sides": "4", "sign": "1", "scope": "every_attack",
    }


def default_damage_component(prefix: str = "damage") -> dict[str, Any]:
    return {
        "id": identifier(prefix), "name": "武器", "dice_count": "1", "dice_sides": "8",
        "flat_bonus": "3", "damage_type": "挥砍", "scope": "every_hit",
        "crit_behavior": "double_dice", "weapon_die": True, "magical": False,
    }


def _normalize_attack_modifier(value: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    return {**default_attack_modifier(prefix), **dict(value), "id": str(value.get("id") or identifier(prefix))}


def _normalize_damage_component(value: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    return {**default_damage_component(prefix), **dict(value), "id": str(value.get("id") or identifier(prefix))}


def _legacy_attack_modifiers(entry: Mapping[str, Any], entry_id: str) -> tuple[list[dict[str, Any]], str]:
    modifiers = []
    if entry.get("bless"):
        modifiers.append({**default_attack_modifier(), "id": f"{entry_id}:legacy-bless", "name": "祝福术"})
    if entry.get("bane"):
        modifiers.append({**default_attack_modifier(), "id": f"{entry_id}:legacy-bane", "name": "灾祸术", "sign": "-1"})
    preset = str(entry.get("preset") or "无")
    if preset == "祝福术 +1d4":
        modifiers.append({**default_attack_modifier(), "id": f"{entry_id}:legacy-preset-bless", "name": "祝福术（预设）"})
        preset = "无"
    elif preset == "灾祸术 -1d4":
        modifiers.append({**default_attack_modifier(), "id": f"{entry_id}:legacy-preset-bane", "name": "灾祸术（预设）", "sign": "-1"})
        preset = "无"
    return modifiers, preset


def _legacy_damage_components(entry: Mapping[str, Any], entry_id: str) -> list[dict[str, Any]]:
    base = {
        **default_damage_component(), "id": f"{entry_id}:base",
        "name": str(entry.get("damage_name") or "伤害"),
        "dice_count": str(entry.get("dice_count", "1")),
        "dice_sides": str(entry.get("dice_sides", "8")),
        "flat_bonus": str(entry.get("flat_bonus", "0")),
        "damage_type": str(entry.get("damage_type") or "挥砍"),
        "weapon_die": bool(entry.get("weapon_die", True)),
        "magical": bool(entry.get("magical", False)),
    }
    output = [base]
    rider = str(entry.get("rider") or "无")
    if rider == "无":
        return output
    scope = "once_selectable" if rider == "偷袭" else "selected_hits"
    crit_behavior = "normal" if rider in ("凶蛮攻击", "野蛮重击") else "double_dice"
    if rider in ("凶蛮攻击", "野蛮重击"):
        scope = "crit_only"
    output.append({
        **default_damage_component(), "id": f"{entry_id}:legacy-rider", "name": rider,
        "dice_count": str(entry.get("rider_dice", "1")),
        "dice_sides": str(entry.get("rider_sides", "6")), "flat_bonus": "0",
        "damage_type": "光耀" if rider == "至圣斩" else str(entry.get("damage_type") or "自定义"),
        "scope": scope, "crit_behavior": crit_behavior,
        "weapon_die": rider in ("凶蛮攻击", "野蛮重击"),
        "magical": bool(entry.get("magical", False)) if rider != "至圣斩" else True,
    })
    return output


def normalize_entry(entry: Mapping[str, Any], index: int = 1, source_version: int = CONFIG_VERSION) -> dict[str, Any]:
    """迁移旧条目并规范化动态命中修正和伤害组件。"""
    normalized = {**default_entry(index), **dict(entry)}
    entry_id = str(normalized["id"])
    if source_version == 1:
        modifiers, preset = _legacy_attack_modifiers(entry, entry_id)
        damages = _legacy_damage_components(entry, entry_id)
        normalized["preset"] = preset
    else:
        modifiers = list(entry.get("attack_modifiers") or [])
        damages = list(entry.get("damage_components") or [])
    normalized["attack_modifiers"] = [
        _normalize_attack_modifier(item, f"{entry_id}:modifier") for item in modifiers
    ]
    if not damages:
        damages = [default_damage_component(f"{entry_id}:damage")]
    normalized["damage_components"] = [
        _normalize_damage_component(item, f"{entry_id}:damage") for item in damages
    ]
    for legacy_key in (
        "bless", "bane", "damage_name", "dice_count", "dice_sides", "flat_bonus",
        "damage_type", "weapon_die", "magical", "rider", "rider_dice", "rider_sides",
    ):
        normalized.pop(legacy_key, None)
    return normalized


def normalize_custom_preset(value: Mapping[str, Any], name: str, source_version: int) -> dict[str, Any]:
    migrated = normalize_entry({"id": f"preset-{name}", **dict(value)}, source_version=source_version)
    excluded = {"id", "name", "target_id", "preset"}
    return {key: item for key, item in migrated.items() if key not in excluded}


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
        "analysis": default_analysis(),
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
    version = int(data.get("config_version", 1))
    if version not in (1, CONFIG_VERSION):
        raise ValueError(f"不支持配置版本 {version}，当前仅支持版本 {CONFIG_VERSION}")

    normalized = deepcopy(dict(data))
    raw_targets = data.get("targets") or []
    targets = [normalize_target(item, index + 1) for index, item in enumerate(raw_targets)]
    if not targets:
        targets = [default_target()]
    raw_entries = data.get("entries") or []
    entries = [normalize_entry(item, index + 1, version) for index, item in enumerate(raw_entries)]
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
        custom_presets={name: normalize_custom_preset(value, name, version) for name, value in dict(data.get("custom_presets") or {}).items()},
        analysis=normalize_analysis(data.get("analysis") if isinstance(data.get("analysis"), Mapping) else None),
        web={"active_view": "quick", **dict(data.get("web") or {})},
    )
    return normalized


def portable_config(data: Mapping[str, Any]) -> dict[str, Any]:
    """生成桌面与网页可互换的配置，排除本机窗口状态。"""
    payload = deepcopy(dict(data))
    payload.pop("window", None)
    payload["config_version"] = CONFIG_VERSION
    return payload


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


def damage_components_from_entry(entry: Mapping[str, Any], *, selectable: bool = True) -> tuple[DamageComponent, ...]:
    output = []
    for item in entry.get("damage_components") or ():
        weapon_die = bool(item.get("weapon_die", False))
        policy = RerollPolicy((1, 2), True, True) if entry.get("great_weapon_fighting") and weapon_die else RerollPolicy()
        scope = ApplicationScope(str(item.get("scope") or "every_hit")) if selectable else ApplicationScope.EVERY_HIT
        output.append(DamageComponent(
            str(item["id"]), str(item.get("name") or "伤害"),
            DiceTerm(int(item.get("dice_count", 1)), int(item.get("dice_sides", 8))),
            int(item.get("flat_bonus", 0)), str(item.get("damage_type") or "挥砍"),
            weapon_die, bool(item.get("magical", False)), scope,
            CritBehavior(str(item.get("crit_behavior") or "double_dice")), policy,
        ))
    if not output:
        raise ValueError("每个结算条目至少需要一个伤害组件")
    return tuple(output)


def component_from_entry(entry: Mapping[str, Any]) -> DamageComponent:
    """兼容旧调用方；新代码应使用 damage_components_from_entry。"""
    return damage_components_from_entry(entry, selectable=False)[0]


def attack_group_from_entry(entry: Mapping[str, Any]) -> AttackGroup:
    components = damage_components_from_entry(entry)
    modifiers = []
    selectable_modifiers = []
    for item in entry.get("attack_modifiers") or ():
        dice = DiceTerm(int(item.get("dice_count", 1)), int(item.get("dice_sides", 4)), int(item.get("sign", 1)))
        if item.get("scope") == "once_selectable":
            selectable_modifiers.append(SelectableAttackModifier(str(item["id"]), str(item.get("name") or "命中修正"), dice))
        else:
            modifiers.append(DiceModifier(str(item.get("name") or "命中修正"), dice))
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
        components=components,
        selectable_attack_modifiers=tuple(selectable_modifiers),
        manual_hit_count=int(entry.get("manual_hit_count", 0)) if entry.get("manual_hits") else None,
        manual_critical_count=int(entry.get("manual_critical_count", 0)) if entry.get("manual_hits") else 0,
    )
    return apply_attack_preset(group, str(entry.get("preset") or "无"))
