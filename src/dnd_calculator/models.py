"""与界面无关的 D&D 5e 2014 结算数据模型。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum


class ResolutionMode(str, Enum):
    ATTACK = "attack"
    SAVE = "save"
    AUTO = "auto"


class RollMode(str, Enum):
    NORMAL = "normal"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"


class SaveOutcome(str, Enum):
    FULL = "full"
    HALF = "half"
    NONE = "none"


class ApplicationScope(str, Enum):
    EVERY_HIT = "every_hit"
    ONCE_SELECTABLE = "once_selectable"
    SELECTED_HITS = "selected_hits"
    CRIT_ONLY = "crit_only"


class AttackModifierScope(str, Enum):
    EVERY_ATTACK = "every_attack"
    ONCE_SELECTABLE = "once_selectable"


class CritBehavior(str, Enum):
    DOUBLE_DICE = "double_dice"
    NORMAL = "normal"


STANDARD_DAMAGE_TYPES: tuple[str, ...] = (
    "强酸", "钝击", "寒冷", "火焰", "力场", "闪电", "黯蚀",
    "穿刺", "毒素", "心灵", "光耀", "挥砍", "雷鸣",
)

STANDARD_ABILITIES: tuple[str, ...] = (
    "力量", "敏捷", "体质", "智力", "感知", "魅力",
)


@dataclass(frozen=True)
class DiceTerm:
    count: int
    sides: int
    sign: int = 1

    def validate(self) -> None:
        if not 0 <= self.count <= 100:
            raise ValueError("骰子数量必须在 0 到 100 之间")
        if not 2 <= self.sides <= 1000:
            raise ValueError("骰子面数必须在 2 到 1000 之间")
        if self.sign not in (-1, 1):
            raise ValueError("骰子符号只能是 +1 或 -1")


@dataclass(frozen=True)
class DiceModifier:
    name: str
    dice: DiceTerm


@dataclass(frozen=True)
class SelectableAttackModifier:
    modifier_id: str
    name: str
    dice: DiceTerm

    def validate(self) -> None:
        if not self.modifier_id.strip():
            raise ValueError("命中修正必须有稳定 ID")
        self.dice.validate()


@dataclass(frozen=True)
class RerollPolicy:
    faces: tuple[int, ...] = ()
    once: bool = True
    weapon_only: bool = False


@dataclass(frozen=True)
class DamageComponent:
    component_id: str
    name: str
    dice: DiceTerm
    flat_bonus: int = 0
    damage_type: str = "挥砍"
    weapon_die: bool = False
    magical: bool = False
    scope: ApplicationScope = ApplicationScope.EVERY_HIT
    crit_behavior: CritBehavior = CritBehavior.DOUBLE_DICE
    reroll: RerollPolicy = field(default_factory=RerollPolicy)

    def validate(self) -> None:
        if not self.component_id.strip():
            raise ValueError("伤害组件必须有稳定 ID")
        self.dice.validate()
        if self.dice.sign != 1:
            raise ValueError("伤害骰不能使用负号；负值请填写固定调整")


@dataclass(frozen=True)
class DamageReduction:
    amount: int
    damage_types: tuple[str, ...] = ()
    nonmagical_only: bool = False


@dataclass(frozen=True)
class Target:
    target_id: str
    name: str
    ac: int = 10
    saves: tuple[tuple[str, int], ...] = ()
    resistances: frozenset[str] = frozenset()
    vulnerabilities: frozenset[str] = frozenset()
    immunities: frozenset[str] = frozenset()
    nonmagical_resistances: frozenset[str] = frozenset()
    crit_immune: bool = False
    reductions: tuple[DamageReduction, ...] = ()

    def save_bonus(self, ability: str) -> int:
        return dict(self.saves).get(ability, 0)

    def validate(self) -> None:
        if not self.target_id.strip():
            raise ValueError("目标必须有稳定 ID")
        if not 1 <= self.ac <= 99:
            raise ValueError(f"{self.name} 的 AC 必须在 1 到 99 之间")


@dataclass(frozen=True)
class AttackGroup:
    group_id: str
    name: str
    target_id: str
    count: int = 1
    attack_bonus: int = 0
    advantage_sources: int = 0
    disadvantage_sources: int = 0
    elven_accuracy: bool = False
    halfling_lucky: bool = False
    crit_range: int = 20
    attack_dice: tuple[DiceModifier, ...] = ()
    power_attack_indices: frozenset[int] = frozenset()
    power_attack_penalty: int = -5
    power_attack_damage: int = 10
    components: tuple[DamageComponent, ...] = ()
    selectable_attack_modifiers: tuple[SelectableAttackModifier, ...] = ()
    manual_hit_count: int | None = None
    manual_critical_count: int = 0

    def validate(self) -> None:
        if not self.group_id.strip():
            raise ValueError("攻击组必须有稳定 ID")
        if not 1 <= self.count <= 100:
            raise ValueError("攻击次数必须在 1 到 100 之间")
        if not 2 <= self.crit_range <= 20:
            raise ValueError("重击范围必须在 2 到 20 之间")
        if self.advantage_sources < 0 or self.disadvantage_sources < 0:
            raise ValueError("优势/劣势来源数不能为负数")
        if self.manual_hit_count is not None:
            if not 0 <= self.manual_hit_count <= self.count:
                raise ValueError("手动命中次数必须在 0 到攻击次数之间")
            if not 0 <= self.manual_critical_count <= self.manual_hit_count:
                raise ValueError("手动重击次数必须在 0 到命中次数之间")
        elif self.manual_critical_count:
            raise ValueError("只有启用手动命中时才能设定手动重击次数")
        for modifier in self.attack_dice:
            modifier.dice.validate()
        for modifier in self.selectable_attack_modifiers:
            modifier.validate()
        for component in self.components:
            component.validate()


@dataclass(frozen=True)
class SaveEffect:
    effect_id: str
    name: str
    target_ids: tuple[str, ...]
    dc: int
    ability: str
    success_outcome: SaveOutcome
    components: tuple[DamageComponent, ...]

    def validate(self) -> None:
        if not 1 <= self.dc <= 99:
            raise ValueError("豁免 DC 必须在 1 到 99 之间")
        if not self.target_ids:
            raise ValueError("至少选择一个目标")
        for component in self.components:
            component.validate()


@dataclass(frozen=True)
class AutoEffect:
    effect_id: str
    name: str
    target_ids: tuple[str, ...]
    components: tuple[DamageComponent, ...]

    def validate(self) -> None:
        if not self.target_ids:
            raise ValueError("至少选择一个目标")
        for component in self.components:
            component.validate()


@dataclass(frozen=True)
class D20Roll:
    original: int
    value: int
    rerolled: bool = False


@dataclass(frozen=True)
class AttackResult:
    attack_id: str
    group_id: str
    group_name: str
    index: int
    target_id: str
    d20_rolls: tuple[D20Roll, ...]
    selected_d20: int
    dice_modifier_total: int
    total: int
    hit: bool
    critical: bool
    power_attack: bool
    explanation: str


@dataclass(frozen=True)
class SaveResult:
    target_id: str
    d20: int
    bonus: int
    total: int
    succeeded: bool


@dataclass(frozen=True)
class RolledDie:
    sides: int
    value: int
    original: int | None = None
    rerolled: bool = False


@dataclass(frozen=True)
class ComponentRoll:
    component_id: str
    name: str
    damage_type: str
    magical: bool
    dice: tuple[RolledDie, ...]
    flat_bonus: int
    raw_total: int


@dataclass(frozen=True)
class DamageTypeResult:
    damage_type: str
    raw: int
    after_reduction: int
    after_save: int
    final: int
    note: str = ""


@dataclass(frozen=True)
class DamageInstanceResult:
    source_id: str
    target_id: str
    critical: bool
    components: tuple[ComponentRoll, ...]
    by_type: tuple[DamageTypeResult, ...]
    total: int


@dataclass(frozen=True)
class ResolutionSession:
    mode: ResolutionMode
    targets: tuple[Target, ...]
    attack_groups: tuple[AttackGroup, ...] = ()
    attack_results: tuple[AttackResult, ...] = ()
    save_effect: SaveEffect | None = None
    save_results: tuple[SaveResult, ...] = ()
    auto_effect: AutoEffect | None = None
    rider_selections: tuple[tuple[str, tuple[str, ...]], ...] = ()
    damage_results: tuple[DamageInstanceResult, ...] = ()
    attack_modifiers_resolved: bool = True
    attack_modifier_selections: tuple[tuple[str, str], ...] = ()

    def selections(self) -> Mapping[str, tuple[str, ...]]:
        return dict(self.rider_selections)
