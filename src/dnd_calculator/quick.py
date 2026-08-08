"""面向快速计算页的一键攻击结算适配层。"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import RulesEngine
from .models import (
    AttackGroup,
    DamageComponent,
    DiceTerm,
    ResolutionSession,
    RollMode,
    Target,
)


@dataclass(frozen=True)
class QuickAttackRequest:
    target_ac: int = 15
    attack_bonus: int = 5
    attack_count: int = 1
    roll_mode: RollMode = RollMode.NORMAL
    crit_range: int = 20
    power_attack: bool = False
    damage_dice_count: int = 1
    damage_die_sides: int = 8
    damage_bonus: int = 3
    manual_hit_count: int | None = None
    manual_critical_count: int = 0

    def validate(self) -> None:
        if self.manual_hit_count is None and not 1 <= self.target_ac <= 99:
            raise ValueError("目标 AC 必须在 1 到 99 之间")
        if not 1 <= self.attack_count <= 100:
            raise ValueError("攻击次数必须在 1 到 100 之间")
        if not 2 <= self.crit_range <= 20:
            raise ValueError("重击范围必须在 2 到 20 之间")
        if self.manual_hit_count is not None:
            if not 0 <= self.manual_hit_count <= self.attack_count:
                raise ValueError("手动命中次数必须在 0 到攻击次数之间")
            if not 0 <= self.manual_critical_count <= self.manual_hit_count:
                raise ValueError("手动重击次数必须在 0 到命中次数之间")
        elif self.manual_critical_count:
            raise ValueError("未启用手动命中时，重击次数必须为 0")
        DiceTerm(self.damage_dice_count, self.damage_die_sides).validate()


@dataclass(frozen=True)
class QuickAttackSummary:
    attack_count: int
    hit_count: int
    critical_count: int
    total_damage: int
    session: ResolutionSession


def resolve_quick_attack(
    request: QuickAttackRequest,
    engine: RulesEngine | None = None,
) -> QuickAttackSummary:
    """把快速页输入转换成正式规则模型，并一次完成命中与伤害。"""
    request.validate()
    engine = engine or RulesEngine()
    target = Target(
        "quick-target",
        "目标",
        ac=request.target_ac if 1 <= request.target_ac <= 99 else 10,
    )
    component = DamageComponent(
        "quick-weapon",
        "武器伤害",
        DiceTerm(request.damage_dice_count, request.damage_die_sides),
        flat_bonus=request.damage_bonus,
        damage_type="挥砍",
        weapon_die=True,
    )
    advantage = 1 if request.roll_mode is RollMode.ADVANTAGE else 0
    disadvantage = 1 if request.roll_mode is RollMode.DISADVANTAGE else 0
    group = AttackGroup(
        "quick-attack",
        "快速攻击",
        target.target_id,
        count=request.attack_count,
        attack_bonus=request.attack_bonus,
        advantage_sources=advantage,
        disadvantage_sources=disadvantage,
        crit_range=request.crit_range,
        power_attack_indices=(
            frozenset(range(request.attack_count)) if request.power_attack else frozenset()
        ),
        components=(component,),
        manual_hit_count=request.manual_hit_count,
        manual_critical_count=request.manual_critical_count,
    )
    session = engine.resolve_attacks((group,), (target,))
    session = engine.resolve_damage(session)
    hits = sum(1 for result in session.attack_results if result.hit)
    criticals = sum(1 for result in session.attack_results if result.critical)
    total = sum(result.total for result in session.damage_results)
    return QuickAttackSummary(request.attack_count, hits, criticals, total, session)
