"""供 Pyodide Web Worker 调用的 JSON 桥接器。"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
from typing import Any, Mapping
from uuid import uuid4

from . import __version__
from .application import (
    CONFIG_VERSION,
    attack_group_from_entry,
    component_from_entry,
    normalize_config,
    targets_from_config,
)
from .engine import RulesEngine, RulesError
from .models import (
    ApplicationScope,
    AutoEffect,
    ResolutionMode,
    ResolutionSession,
    RollMode,
    SaveEffect,
)
from .presets import SAVE_PRESETS
from .quick import QuickAttackRequest, resolve_quick_attack


def jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [jsonable(item) for item in value]
    return value


class WebBridge:
    def __init__(self, engine: RulesEngine | None = None):
        self.engine = engine or RulesEngine()
        self.sessions: dict[str, list[ResolutionSession]] = {}

    @staticmethod
    def init() -> dict[str, Any]:
        return {
            "version": __version__,
            "config_version": CONFIG_VERSION,
            "methods": [
                "init", "resolveQuick", "startAdvanced", "resolveAttackDamage",
                "reroll", "disposeSession",
            ],
        }

    def resolve_quick(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = QuickAttackRequest(
            target_ac=int(payload.get("target_ac", 15)),
            attack_bonus=int(payload.get("attack_bonus", 5)),
            attack_count=int(payload.get("attack_count", 1)),
            roll_mode=RollMode(str(payload.get("roll_mode", RollMode.NORMAL.value))),
            crit_range=int(payload.get("crit_range", 20)),
            power_attack=bool(payload.get("power_attack", False)),
            damage_dice_count=int(payload.get("damage_dice_count", 1)),
            damage_die_sides=int(payload.get("damage_die_sides", 8)),
            damage_bonus=int(payload.get("damage_bonus", 3)),
            manual_hit_count=(
                int(payload["manual_hit_count"])
                if payload.get("manual_hit_count") is not None
                else None
            ),
            manual_critical_count=int(payload.get("manual_critical_count", 0)),
        )
        summary = resolve_quick_attack(request, self.engine)
        return jsonable(summary)

    def start_advanced(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        config = normalize_config(payload)
        targets = targets_from_config(config["targets"])
        entries = config["entries"]
        sessions: list[ResolutionSession] = []
        attack_groups = [
            attack_group_from_entry(entry)
            for entry in entries
            if entry.get("mode") == ResolutionMode.ATTACK.value
        ]
        if attack_groups:
            sessions.append(self.engine.resolve_attacks(attack_groups, targets))
        for entry in entries:
            mode = entry.get("mode")
            target_ids = (
                tuple(target.target_id for target in targets)
                if entry.get("all_targets")
                else (str(entry.get("target_id") or ""),)
            )
            component = component_from_entry(entry)
            if mode == ResolutionMode.SAVE.value:
                outcome_name = str(entry.get("save_outcome") or "成功半伤")
                if outcome_name not in SAVE_PRESETS:
                    raise ValueError(f"未知豁免结果：{outcome_name}")
                effect = SaveEffect(
                    str(entry["id"]), str(entry.get("name") or "豁免伤害"), target_ids,
                    int(entry.get("dc", 15)), str(entry.get("save_ability") or "敏捷"),
                    SAVE_PRESETS[outcome_name], (component,),
                )
                sessions.append(self.engine.resolve_damage(self.engine.resolve_saves(effect, targets)))
            elif mode == ResolutionMode.AUTO.value:
                effect = AutoEffect(
                    str(entry["id"]), str(entry.get("name") or "自动伤害"), target_ids,
                    (component,),
                )
                sessions.append(self.engine.resolve_damage(self.engine.resolve_auto(effect, targets)))

        session_id = uuid4().hex
        self.sessions[session_id] = sessions
        return self._advanced_response(session_id)

    def resolve_attack_damage(
        self, session_id: str, selections: Mapping[str, list[str]] | None = None
    ) -> dict[str, Any]:
        sessions = self._require_session(session_id)
        updated = []
        for session in sessions:
            updated.append(
                self.engine.resolve_damage(session, selections or {})
                if session.mode is ResolutionMode.ATTACK
                else session
            )
        self.sessions[session_id] = updated
        return self._advanced_response(session_id)

    def reroll(self, session_id: str, references: list[list[Any]]) -> dict[str, Any]:
        refs = [(str(item[0]), str(item[1]), int(item[2])) for item in references]
        sessions = self._require_session(session_id)
        self.sessions[session_id] = [self.engine.reroll_selected(session, refs) for session in sessions]
        return self._advanced_response(session_id)

    def dispose_session(self, session_id: str) -> dict[str, bool]:
        return {"disposed": self.sessions.pop(session_id, None) is not None}

    def _require_session(self, session_id: str) -> list[ResolutionSession]:
        if session_id not in self.sessions:
            raise RulesError("结算会话不存在或页面已经刷新，请重新投掷检定")
        return self.sessions[session_id]

    def _advanced_response(self, session_id: str) -> dict[str, Any]:
        sessions = self._require_session(session_id)
        riders = []
        for session in sessions:
            if session.mode is not ResolutionMode.ATTACK:
                continue
            hits = [result for result in session.attack_results if result.hit]
            for group in session.attack_groups:
                for component in group.components:
                    if component.scope in (ApplicationScope.ONCE_SELECTABLE, ApplicationScope.SELECTED_HITS):
                        riders.append({
                            "component_id": component.component_id,
                            "name": component.name,
                            "scope": component.scope.value,
                            "attacks": [jsonable(hit) for hit in hits if hit.group_id == group.group_id],
                        })
        return {"session_id": session_id, "sessions": jsonable(sessions), "selectable_riders": riders}


_BRIDGE = WebBridge()


def dispatch_json(method: str, payload_json: str = "{}") -> str:
    """统一 JSON 边界：成功与失败都返回可序列化对象。"""
    try:
        payload = json.loads(payload_json or "{}")
        if method == "init":
            data = _BRIDGE.init()
        elif method == "resolveQuick":
            data = _BRIDGE.resolve_quick(payload)
        elif method == "startAdvanced":
            data = _BRIDGE.start_advanced(payload)
        elif method == "resolveAttackDamage":
            data = _BRIDGE.resolve_attack_damage(str(payload["session_id"]), payload.get("selections"))
        elif method == "reroll":
            data = _BRIDGE.reroll(str(payload["session_id"]), list(payload.get("references") or []))
        elif method == "disposeSession":
            data = _BRIDGE.dispose_session(str(payload["session_id"]))
        else:
            raise ValueError(f"未知网页桥接方法：{method}")
        return json.dumps({"ok": True, "data": data}, ensure_ascii=False)
    except (KeyError, TypeError, ValueError, RulesError) as exc:
        return json.dumps(
            {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}},
            ensure_ascii=False,
        )
