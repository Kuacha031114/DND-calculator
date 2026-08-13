"""跨桌面与网页共享的命中率、期望伤害和战斗时长分析。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from functools import lru_cache
from itertools import product
from typing import Any
from uuid import uuid4

ANALYSIS_ROLL_MODES = ("normal", "advantage", "disadvantage", "elven_accuracy")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_build(index: int = 1) -> dict[str, Any]:
    return {
        "id": _id("build"),
        "name": "常规攻击" if index == 1 else f"方案 {index}",
        "enabled": True,
        "attack_bonus": "7",
        "attacks_per_round": "2",
        "roll_mode": "normal",
        "crit_range": "20",
        "damage_dice_count": "1",
        "damage_die_sides": "8",
        "damage_bonus": "4",
        "power_attack": False,
        "crit_extra_dice": "0",
        "rider_dice_count": "0",
        "rider_die_sides": "6",
        "rider_bonus": "0",
        "rider_doubles_on_crit": True,
        "guaranteed_damage": "0",
    }


def default_analysis() -> dict[str, Any]:
    regular = default_build(1)
    power = default_build(2)
    power.update(name="减 5 加 10", enabled=False, power_attack=True)
    return {
        "target_ac": "15",
        "monster_count": "1",
        "hp_each": "40",
        "party_uptime_percent": "85",
        "damage_multiplier": "1",
        "desired_rounds": "4",
        "builds": [regular, power],
    }


def normalize_analysis(value: Mapping[str, Any] | None) -> dict[str, Any]:
    defaults = default_analysis()
    if not isinstance(value, Mapping):
        return defaults
    source = deepcopy(dict(value))
    raw_builds = source.get("builds")
    if isinstance(raw_builds, list) and raw_builds:
        builds = []
        for index, raw in enumerate(raw_builds, 1):
            item = dict(raw) if isinstance(raw, Mapping) else {}
            builds.append({**default_build(index), **item, "id": str(item.get("id") or _id("build"))})
    else:
        builds = defaults["builds"]
    return {**defaults, **source, "builds": builds}


def _integer(value: object, label: str, minimum: int, maximum: int) -> int:
    text = str(value).strip()
    if not text or (text[0] == "-" and not text[1:].isdigit()) or (text[0] != "-" and not text.isdigit()):
        raise ValueError(f"{label} 必须是整数")
    parsed = int(text)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{label} 必须在 {minimum} 到 {maximum} 之间")
    return parsed


def _decimal(value: object, label: str, minimum: float, maximum: float) -> float:
    text = str(value).strip()
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        raise ValueError(f"{label} 必须是数字") from None
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{label} 必须在 {minimum:g} 到 {maximum:g} 之间")
    return parsed


@lru_cache(maxsize=4)
def selected_d20_distribution(mode: str) -> tuple[float, ...]:
    if mode not in ANALYSIS_ROLL_MODES:
        raise ValueError(f"未知投骰方式：{mode}")
    count = 3 if mode == "elven_accuracy" else 1 if mode == "normal" else 2
    probabilities = [0.0] * 21
    weight = 1 / (20 ** count)
    for values in product(range(1, 21), repeat=count):
        selected = min(values) if mode == "disadvantage" else max(values)
        probabilities[selected] += weight
    return tuple(probabilities)


def attack_probabilities(target_ac: int, attack_bonus: int, mode: str, crit_range: int) -> dict[str, float]:
    distribution = selected_d20_distribution(mode)
    normal = critical = 0.0
    for d20 in range(1, 21):
        probability = distribution[d20]
        if d20 == 1:
            continue
        if d20 >= crit_range:
            critical += probability
        elif d20 + attack_bonus >= target_ac:
            normal += probability
    return {"normal": normal, "critical": critical, "hit": normal + critical}


def expected_damage(count: int, sides: int, flat: int) -> float:
    """精确计算 E[max(0, 骰子总和 + 固定值)]。"""
    if flat >= 0:
        return count * (sides + 1) / 2 + flat
    if count == 0:
        return float(max(0, flat))
    distribution = [1.0]
    for _ in range(count):
        next_distribution = [0.0] * (len(distribution) + sides)
        for total, probability in enumerate(distribution):
            for face in range(1, sides + 1):
                next_distribution[total + face] += probability / sides
        distribution = next_distribution
    return sum(probability * max(0, total + flat) for total, probability in enumerate(distribution))


def analyze_build(profile: Mapping[str, Any], target_ac: int) -> dict[str, Any]:
    name = str(profile.get("name") or "未命名方案")
    power = bool(profile.get("power_attack", False))
    attack_bonus = _integer(profile.get("attack_bonus", "7"), f"{name}的命中加值", -99, 99) - (5 if power else 0)
    attacks = _integer(profile.get("attacks_per_round", "2"), f"{name}的每轮攻击次数", 1, 100)
    crit_range = _integer(profile.get("crit_range", "20"), f"{name}的重击下限", 2, 20)
    dice_count = _integer(profile.get("damage_dice_count", "1"), f"{name}的伤害骰数量", 0, 50)
    sides = _integer(profile.get("damage_die_sides", "8"), f"{name}的伤害骰面数", 2, 100)
    damage_bonus = _integer(profile.get("damage_bonus", "4"), f"{name}的伤害加值", -100, 500) + (10 if power else 0)
    extra = _integer(profile.get("crit_extra_dice", "0"), f"{name}的重击额外骰", 0, 50)
    rider_count = _integer(profile.get("rider_dice_count", "0"), f"{name}的首次命中附伤骰", 0, 50)
    rider_sides = _integer(profile.get("rider_die_sides", "6"), f"{name}的附伤骰面数", 2, 100)
    rider_bonus = _integer(profile.get("rider_bonus", "0"), f"{name}的附伤加值", -100, 500)
    guaranteed = _decimal(profile.get("guaranteed_damage", "0"), f"{name}的每轮固定伤害", 0, 10000)
    probabilities = attack_probabilities(target_ac, attack_bonus, str(profile.get("roll_mode") or "normal"), crit_range)
    normal_damage = expected_damage(dice_count, sides, damage_bonus)
    critical_damage = expected_damage(dice_count * 2 + extra, sides, damage_bonus)
    per_attack = probabilities["normal"] * normal_damage + probabilities["critical"] * critical_damage
    miss = 1 - probabilities["hit"]
    first_hit_factor = 0 if probabilities["hit"] == 0 else (1 - miss ** attacks) / probabilities["hit"]
    normal_rider = expected_damage(rider_count, rider_sides, rider_bonus)
    critical_rider = expected_damage(rider_count * 2 if profile.get("rider_doubles_on_crit", True) else rider_count, rider_sides, rider_bonus)
    rider_damage = first_hit_factor * (
        probabilities["normal"] * normal_rider + probabilities["critical"] * critical_rider
    )
    return {
        "id": str(profile.get("id") or ""), "name": name,
        "included_in_party": bool(profile.get("enabled", True)),
        "hit_probability": probabilities["hit"], "normal_hit_probability": probabilities["normal"],
        "critical_probability": probabilities["critical"],
        "at_least_one_hit_probability": 1 - miss ** attacks,
        "at_least_one_critical_probability": 1 - (1 - probabilities["critical"]) ** attacks,
        "expected_hits": attacks * probabilities["hit"], "damage_per_attack": per_attack,
        "rider_damage": rider_damage, "guaranteed_damage": guaranteed,
        "dpr": attacks * per_attack + rider_damage + guaranteed,
    }


def analyze_encounter(config: Mapping[str, Any], target_ac_override: int | None = None) -> dict[str, Any]:
    target_ac = target_ac_override if target_ac_override is not None else _integer(config.get("target_ac", "15"), "目标 AC", 1, 99)
    monster_count = _integer(config.get("monster_count", "1"), "怪物数量", 1, 100)
    hp_each = _decimal(config.get("hp_each", "40"), "每只怪物 HP", 1, 100000)
    uptime = _decimal(config.get("party_uptime_percent", "85"), "队伍输出在线率", 1, 100) / 100
    multiplier = _decimal(config.get("damage_multiplier", "1"), "伤害结算倍率", 0.01, 10)
    desired_rounds = _decimal(config.get("desired_rounds", "4"), "目标战斗轮数", 0.1, 100)
    raw_builds = config.get("builds")
    if not isinstance(raw_builds, Sequence) or isinstance(raw_builds, (str, bytes)) or not raw_builds:
        raise ValueError("至少需要一个构筑方案")
    builds = []
    for profile in raw_builds:
        if not isinstance(profile, Mapping):
            raise ValueError("构筑方案必须是对象")
        builds.append(analyze_build(profile, target_ac))
    included = [build for build in builds if build["included_in_party"]]
    raw_dpr = sum(build["dpr"] for build in included)
    adjusted = raw_dpr * uptime * multiplier
    total_hp = monster_count * hp_each
    return {
        "builds": builds, "party_build_count": len(included), "raw_party_dpr": raw_dpr,
        "adjusted_party_dpr": adjusted, "total_monster_hp": total_hp,
        "estimated_rounds": total_hp / adjusted if adjusted > 0 else None,
        "suggested_hp_each": adjusted * desired_rounds / monster_count,
        "suggested_monster_count": adjusted * desired_rounds / hp_each,
    }


def analyze_encounter_bundle(config: Mapping[str, Any], sensitivity_acs: Sequence[int]) -> dict[str, Any]:
    result = analyze_encounter(config)
    sensitivity = []
    for raw_ac in sensitivity_acs:
        ac = int(raw_ac)
        if not 1 <= ac <= 99:
            raise ValueError("敏感性 AC 必须在 1 到 99 之间")
        sensitivity.append({"ac": ac, "result": analyze_encounter(config, ac)})
    return {"result": result, "sensitivity": sensitivity}
