"""默认展示的低门槛快速攻击界面。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable, Mapping

from .engine import RulesEngine, format_d20_rolls
from .models import RollMode
from .quick import QuickAttackRequest, QuickAttackSummary, resolve_quick_attack


QUICK_DEFAULTS = {
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

MODE_TO_RULE = {
    "普通": RollMode.NORMAL,
    "优势": RollMode.ADVANTAGE,
    "劣势": RollMode.DISADVANTAGE,
}


class QuickAttackPage(tk.Frame):
    BG = "#e8dcc0"
    CARD = "#f5ecd6"
    INPUT = "#fbf6e8"
    BORDER = "#b89968"
    TEXT = "#3a2c1a"
    SUB = "#7d6a4d"
    GOLD = "#8a6d3b"
    RED = "#9c3b2e"
    GREEN = "#486b45"

    def __init__(
        self,
        parent,
        *,
        family: str,
        mono: str,
        data: Mapping[str, object] | None = None,
        engine: RulesEngine | None = None,
        on_advanced: Callable[[], None],
        on_import_advanced: Callable[[QuickAttackRequest], None],
    ):
        super().__init__(parent, bg=self.BG)
        self.family = family
        self.mono = mono
        self.engine = engine or RulesEngine()
        self.on_advanced = on_advanced
        self.on_import_advanced = on_import_advanced
        self.summary: QuickAttackSummary | None = None
        self.details_visible = False
        self.help_visible = False
        values = {**QUICK_DEFAULTS, **(data or {})}

        self.target_ac = tk.StringVar(value=str(values["target_ac"]))
        self.attack_bonus = tk.StringVar(value=str(values["attack_bonus"]))
        self.attack_count = tk.StringVar(value=str(values["attack_count"]))
        self.roll_mode = tk.StringVar(value=str(values["roll_mode"]))
        self.crit_range = tk.StringVar(value=str(values["crit_range"]))
        self.power_attack = tk.BooleanVar(value=bool(values["power_attack"]))
        self.damage_dice_count = tk.StringVar(value=str(values["damage_dice_count"]))
        self.damage_die_sides = tk.StringVar(value=str(values["damage_die_sides"]))
        self.damage_bonus = tk.StringVar(value=str(values["damage_bonus"]))
        self.manual_hits = tk.BooleanVar(value=bool(values["manual_hits"]))
        self.manual_hit_count = tk.StringVar(value=str(values["manual_hit_count"]))
        self.manual_critical_count = tk.StringVar(value=str(values["manual_critical_count"]))
        self.error_vars = {
            key: tk.StringVar(value="")
            for key in (
                "target_ac", "attack_bonus", "attack_count", "crit_range",
                "damage_dice_count", "damage_die_sides", "damage_bonus",
                "manual_hit_count", "manual_critical_count",
            )
        }
        self.result_hint = tk.StringVar(value="填好上面的数值后，点击“立即结算”。")
        self.hit_text = tk.StringVar(value="—")
        self.crit_text = tk.StringVar(value="—")
        self.damage_text = tk.StringVar(value="—")
        self._build()
        self._attach_traces()

    def _build(self) -> None:
        body = tk.Frame(self, bg=self.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=(14, 16))
        self.form_column = tk.Frame(body, bg=self.BG)
        self.form_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        intro = tk.Frame(self.form_column, bg=self.BG)
        intro.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            intro,
            text="快速计算",
            bg=self.BG,
            fg=self.TEXT,
            font=(self.family, 20, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            intro,
            text="普通攻击只需三步，默认示例可以直接投掷",
            bg=self.BG,
            fg=self.SUB,
            font=(self.family, 11),
        ).pack(side=tk.LEFT, padx=14, pady=(5, 0))
        ttk.Button(intro, text="使用帮助", command=self.toggle_help).pack(side=tk.RIGHT)

        workflow = tk.Frame(self.form_column, bg=self.BG)
        workflow.pack(fill=tk.BOTH, expand=True)
        input_column = tk.Frame(workflow, bg=self.BG)
        input_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        result_column = tk.Frame(workflow, bg=self.BG)
        result_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        step1 = self._card(input_column, "1", "填写目标", "只需要知道目标的护甲等级 AC")
        fields = tk.Frame(step1, bg=self.CARD)
        fields.pack(fill=tk.X)
        self._number_field(fields, "目标 AC", self.target_ac, "target_ac", 8).pack(side=tk.LEFT)
        self._tip_button(fields, "AC", "攻击总值达到或超过 AC 即命中；自然 20 自动命中，自然 1 自动未命中。")
        tk.Checkbutton(
            fields,
            text="不知道 AC，手动指定命中",
            variable=self.manual_hits,
            command=self._update_manual_mode,
            bg=self.CARD,
            activebackground=self.CARD,
            selectcolor=self.INPUT,
            fg=self.TEXT,
            font=(self.family, 10, "bold"),
        ).pack(side=tk.LEFT, padx=(18, 0), pady=(2, 0))

        self.manual_fields = tk.Frame(step1, bg=self.CARD)
        self._number_field(
            self.manual_fields, "命中次数", self.manual_hit_count, "manual_hit_count", 8
        ).pack(side=tk.LEFT, padx=(0, 18))
        self._number_field(
            self.manual_fields, "其中重击", self.manual_critical_count, "manual_critical_count", 8
        ).pack(side=tk.LEFT)
        tk.Label(
            self.manual_fields,
            text="手动模式不投 d20，不使用 AC 和命中加值",
            bg=self.CARD,
            fg=self.SUB,
            font=(self.family, 9),
        ).pack(side=tk.LEFT, padx=12, pady=(0, 12))
        self._update_manual_mode()

        step2 = self._card(input_column, "2", "填写本次攻击", "常用选项都在这里")
        top = tk.Frame(step2, bg=self.CARD)
        top.pack(fill=tk.X, pady=(0, 8))
        self._number_field(top, "命中加值", self.attack_bonus, "attack_bonus", 8).pack(side=tk.LEFT, padx=(0, 18))
        self._number_field(top, "攻击次数", self.attack_count, "attack_count", 8).pack(side=tk.LEFT)

        mode_row = tk.Frame(step2, bg=self.CARD)
        mode_row.pack(fill=tk.X, pady=5)
        tk.Label(mode_row, text="攻击状态", bg=self.CARD, fg=self.TEXT, font=(self.family, 11, "bold")).pack(side=tk.LEFT, padx=(0, 12))
        for label in ("普通", "优势", "劣势"):
            tk.Radiobutton(
                mode_row,
                text=label,
                value=label,
                variable=self.roll_mode,
                indicatoron=False,
                width=7,
                bg=self.INPUT,
                selectcolor=self.GOLD,
                fg=self.TEXT,
                activebackground="#ede0c4",
                font=(self.family, 10),
                padx=4,
                pady=4,
            ).pack(side=tk.LEFT, padx=2)
        self._tip_button(mode_row, "优势/劣势", "优势投两颗 d20 取高，劣势投两颗 d20 取低。")

        rules = tk.Frame(step2, bg=self.CARD)
        rules.pack(fill=tk.X, pady=5)
        self._number_field(rules, "重击下限", self.crit_range, "crit_range", 8).pack(side=tk.LEFT, padx=(0, 18))
        power = tk.Frame(rules, bg=self.CARD)
        power.pack(side=tk.LEFT, pady=(1, 0))
        tk.Checkbutton(
            power,
            text="启用 -5/+10",
            variable=self.power_attack,
            bg=self.CARD,
            activebackground=self.CARD,
            selectcolor=self.INPUT,
            fg=self.TEXT,
            font=(self.family, 11, "bold"),
        ).pack(anchor="w")
        tk.Label(power, text="命中 -5，伤害 +10", bg=self.CARD, fg=self.SUB, font=(self.family, 9)).pack(anchor="w", padx=4)

        dice_row = tk.Frame(step2, bg=self.CARD)
        dice_row.pack(fill=tk.X, pady=(8, 0))
        tk.Label(dice_row, text="伤害骰", bg=self.CARD, fg=self.TEXT, font=(self.family, 11, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self._bare_number(dice_row, self.damage_dice_count, "damage_dice_count", 5).pack(side=tk.LEFT)
        tk.Label(dice_row, text=" d ", bg=self.CARD, fg=self.TEXT, font=(self.family, 12)).pack(side=tk.LEFT)
        self._bare_number(dice_row, self.damage_die_sides, "damage_die_sides", 5).pack(side=tk.LEFT)
        tk.Label(dice_row, text="  +  ", bg=self.CARD, fg=self.TEXT, font=(self.family, 12)).pack(side=tk.LEFT)
        self._bare_number(dice_row, self.damage_bonus, "damage_bonus", 6).pack(side=tk.LEFT)
        tk.Label(dice_row, text="伤害加值", bg=self.CARD, fg=self.SUB, font=(self.family, 9)).pack(side=tk.LEFT, padx=8)
        self._tip_button(dice_row, "命中与伤害加值", "命中加值和伤害加值都可直接修改。例如长剑 1d8+3：数量填 1，骰面填 8，伤害加值填 3。")

        action = tk.Frame(input_column, bg=self.BG)
        action.pack(fill=tk.X, pady=12)
        self.roll_button = ttk.Button(
            action,
            text="🎲  立即结算",
            command=self.run,
            style="Accent.TButton",
            padding=(38, 12),
        )
        self.roll_button.pack()

        step3 = self._card(result_column, "3", "查看结果", "先看摘要，需要时再展开明细")
        tk.Label(step3, textvariable=self.result_hint, bg=self.CARD, fg=self.SUB, font=(self.family, 10)).pack(anchor="w")
        summary = tk.Frame(step3, bg=self.CARD)
        summary.pack(fill=tk.X, pady=10)
        self._summary_item(summary, "命中", self.hit_text, self.GREEN).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self._summary_item(summary, "重击", self.crit_text, self.GOLD).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._summary_item(summary, "总伤害", self.damage_text, self.RED).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        result_actions = tk.Frame(step3, bg=self.CARD)
        result_actions.pack(fill=tk.X)
        self.detail_button = ttk.Button(result_actions, text="查看每次投掷明细 ▼", command=self.toggle_details, state=tk.DISABLED)
        self.detail_button.pack(side=tk.LEFT)
        ttk.Button(result_actions, text="再投一次", command=self.run).pack(side=tk.LEFT, padx=6)
        self.details = ScrolledText(
            step3,
            height=7,
            font=(self.mono, 10),
            bg=self.INPUT,
            fg=self.TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            state=tk.DISABLED,
        )

        advanced = tk.Frame(result_column, bg=self.BG)
        advanced.pack(fill=tk.X, pady=(10, 0))
        tk.Label(
            advanced,
            text="需要偷袭、至圣斩、多目标或豁免法术？",
            bg=self.BG,
            fg=self.SUB,
            font=(self.family, 10),
        ).pack(anchor="w", pady=(0, 6))
        buttons = tk.Frame(advanced, bg=self.BG)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="进入高级工作台", command=self.on_advanced).pack(side=tk.LEFT)
        ttk.Button(buttons, text="在高级模式继续编辑", command=self.import_to_advanced).pack(side=tk.LEFT, padx=6)

        self.help_panel = tk.Frame(body, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, width=270)
        self.help_panel.pack_propagate(False)
        tk.Label(self.help_panel, text="使用帮助", bg=self.CARD, fg=self.GOLD, font=(self.family, 15, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        help_text = (
            "最常用的流程\n"
            "1. 填写敌人的 AC\n"
            "2. 填写角色命中加值和伤害骰\n"
            "3. 点击“立即结算”\n\n"
            "不知道 AC 时，勾选“手动指定命中”，填写命中和重击次数。\n\n"
            "常见例子\n"
            "长剑：1d8 + 属性调整值\n"
            "巨剑：2d6 + 属性调整值\n\n"
            "重击会将伤害骰数量翻倍，但不会翻倍固定伤害。\n\n"
            "更复杂的职业能力、豁免法术和多个目标请使用高级工作台。"
        )
        tk.Label(
            self.help_panel,
            text=help_text,
            justify=tk.LEFT,
            wraplength=230,
            bg=self.CARD,
            fg=self.TEXT,
            font=(self.family, 10),
        ).pack(anchor="nw", padx=14, pady=6)
        ttk.Button(self.help_panel, text="关闭帮助", command=self.toggle_help).pack(anchor="w", padx=14, pady=10)

    def _card(self, parent, number: str, title: str, subtitle: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=self.BORDER)
        outer.pack(fill=tk.X, pady=5)
        card = tk.Frame(outer, bg=self.CARD)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        header = tk.Frame(card, bg=self.CARD)
        header.pack(fill=tk.X, padx=14, pady=(10, 7))
        tk.Label(header, text=number, bg=self.GOLD, fg="white", font=(self.family, 12, "bold"), width=2).pack(side=tk.LEFT)
        tk.Label(header, text=title, bg=self.CARD, fg=self.TEXT, font=(self.family, 14, "bold")).pack(side=tk.LEFT, padx=8)
        tk.Label(header, text=subtitle, bg=self.CARD, fg=self.SUB, font=(self.family, 9)).pack(side=tk.LEFT, padx=8, pady=(3, 0))
        body = tk.Frame(card, bg=self.CARD)
        body.pack(fill=tk.X, padx=16, pady=(0, 12))
        return body

    def _number_field(self, parent, label: str, variable: tk.StringVar, key: str, width: int) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.CARD)
        tk.Label(frame, text=label, bg=self.CARD, fg=self.TEXT, font=(self.family, 11, "bold")).pack(anchor="w")
        tk.Entry(frame, textvariable=variable, width=width, bg=self.INPUT, fg=self.TEXT, relief=tk.FLAT, font=(self.family, 12)).pack(anchor="w", ipady=4)
        tk.Label(frame, textvariable=self.error_vars[key], bg=self.CARD, fg=self.RED, font=(self.family, 8)).pack(anchor="w")
        return frame

    def _bare_number(self, parent, variable: tk.StringVar, key: str, width: int) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.CARD)
        tk.Entry(frame, textvariable=variable, width=width, justify=tk.CENTER, bg=self.INPUT, fg=self.TEXT, relief=tk.FLAT, font=(self.family, 12)).pack(ipady=4)
        tk.Label(frame, textvariable=self.error_vars[key], bg=self.CARD, fg=self.RED, font=(self.family, 8)).pack()
        return frame

    def _tip_button(self, parent, title: str, text: str) -> None:
        tk.Button(
            parent,
            text="?",
            command=lambda: messagebox.showinfo(title, text, parent=self),
            bg=self.CARD,
            fg=self.GOLD,
            relief=tk.FLAT,
            font=(self.family, 10, "bold"),
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=8)

    def _summary_item(self, parent, label: str, variable: tk.StringVar, color: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.INPUT, highlightbackground=self.BORDER, highlightthickness=1)
        tk.Label(frame, text=label, bg=self.INPUT, fg=self.SUB, font=(self.family, 10)).pack(pady=(7, 0))
        tk.Label(frame, textvariable=variable, bg=self.INPUT, fg=color, font=(self.family, 22, "bold")).pack(pady=(0, 7))
        return frame

    def _attach_traces(self) -> None:
        variables = (
            self.target_ac, self.attack_bonus, self.attack_count, self.roll_mode,
            self.crit_range, self.power_attack, self.damage_dice_count,
            self.damage_die_sides, self.damage_bonus, self.manual_hits,
            self.manual_hit_count, self.manual_critical_count,
        )
        for variable in variables:
            variable.trace_add("write", self._mark_stale)
        self.manual_hits.trace_add("write", lambda *_args: self._update_manual_mode())

    def _update_manual_mode(self) -> None:
        if not hasattr(self, "manual_fields"):
            return
        if self.manual_hits.get():
            self.manual_fields.pack(fill=tk.X, pady=(7, 0))
        else:
            self.manual_fields.pack_forget()

    def _mark_stale(self, *_args) -> None:
        if self.summary is not None:
            self.result_hint.set("设置已改变，点击“立即结算”更新结果。")

    def _parse_int(self, key: str, variable: tk.StringVar, minimum: int, maximum: int) -> int | None:
        try:
            value = int(variable.get())
        except ValueError:
            self.error_vars[key].set("请输入整数")
            return None
        if not minimum <= value <= maximum:
            self.error_vars[key].set(f"范围 {minimum}–{maximum}")
            return None
        return value

    def request(self) -> QuickAttackRequest | None:
        for variable in self.error_vars.values():
            variable.set("")
        attack_count = self._parse_int("attack_count", self.attack_count, 1, 100)
        manual_hits = self.manual_hits.get()
        target_ac = 10 if manual_hits else self._parse_int("target_ac", self.target_ac, 1, 99)
        manual_hit_count = None
        manual_critical_count = 0
        if manual_hits:
            manual_hit_count = self._parse_int(
                "manual_hit_count", self.manual_hit_count, 0, attack_count or 100
            )
            manual_critical_count = self._parse_int(
                "manual_critical_count", self.manual_critical_count, 0, manual_hit_count or 0
            )
            if manual_hit_count is None or manual_critical_count is None:
                self.result_hint.set("请修正红色提示的手动命中输入。")
                return None
        values = {
            "target_ac": target_ac,
            "attack_bonus": self._parse_int("attack_bonus", self.attack_bonus, -99, 99),
            "attack_count": attack_count,
            "crit_range": self._parse_int("crit_range", self.crit_range, 2, 20),
            "damage_dice_count": self._parse_int("damage_dice_count", self.damage_dice_count, 0, 100),
            "damage_die_sides": self._parse_int("damage_die_sides", self.damage_die_sides, 2, 1000),
            "damage_bonus": self._parse_int("damage_bonus", self.damage_bonus, -999, 999),
        }
        if any(value is None for value in values.values()):
            self.result_hint.set("请修正红色提示的输入项。")
            return None
        return QuickAttackRequest(
            target_ac=values["target_ac"],
            attack_bonus=values["attack_bonus"],
            attack_count=values["attack_count"],
            roll_mode=MODE_TO_RULE.get(self.roll_mode.get(), RollMode.NORMAL),
            crit_range=values["crit_range"],
            power_attack=self.power_attack.get(),
            damage_dice_count=values["damage_dice_count"],
            damage_die_sides=values["damage_die_sides"],
            damage_bonus=values["damage_bonus"],
            manual_hit_count=manual_hit_count,
            manual_critical_count=manual_critical_count or 0,
        )

    def run(self) -> None:
        request = self.request()
        if request is None:
            return
        self.summary = resolve_quick_attack(request, self.engine)
        self.hit_text.set(f"{self.summary.hit_count}/{self.summary.attack_count}")
        self.crit_text.set(str(self.summary.critical_count))
        self.damage_text.set(str(self.summary.total_damage))
        self.result_hint.set("结算完成。摘要如下，明细可随时展开核对。")
        self.detail_button.configure(state=tk.NORMAL)
        self._render_details()

    def _render_details(self) -> None:
        if not self.summary:
            return
        damage_by_source = {result.source_id: result for result in self.summary.session.damage_results}
        lines = []
        for attack in self.summary.session.attack_results:
            status = "★ 重击" if attack.critical else ("✔ 命中" if attack.hit else "✘ 未命中")
            rolls = format_d20_rolls(attack.d20_rolls) if attack.d20_rolls else "未投 d20"
            line = f"第 {attack.index + 1} 次　[{rolls}]　{attack.explanation}　{status}"
            damage = damage_by_source.get(attack.attack_id)
            if damage:
                dice = [
                    f"{component.name}({','.join(str(die.value) for die in component.dice)})"
                    for component in damage.components
                ]
                line += f"\n           伤害 {' + '.join(dice)} = {damage.total}"
            lines.append(line)
        self.details.configure(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", "\n\n".join(lines))
        self.details.configure(state=tk.DISABLED)

    def toggle_details(self) -> None:
        if not self.summary:
            return
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.details.pack(fill=tk.X, pady=(8, 0))
            self.detail_button.configure(text="收起每次投掷明细 ▲")
        else:
            self.details.pack_forget()
            self.detail_button.configure(text="查看每次投掷明细 ▼")

    def toggle_help(self) -> None:
        self.help_visible = not self.help_visible
        if self.help_visible:
            self.help_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0), before=self.form_column)
        else:
            self.help_panel.pack_forget()

    def import_to_advanced(self) -> None:
        request = self.request()
        if request is not None:
            self.on_import_advanced(request)

    def reset_defaults(self) -> None:
        for key, default in QUICK_DEFAULTS.items():
            variable = getattr(self, key)
            variable.set(default)
        self._update_manual_mode()

    def config_data(self) -> dict[str, object]:
        return {
            "target_ac": self.target_ac.get(),
            "attack_bonus": self.attack_bonus.get(),
            "attack_count": self.attack_count.get(),
            "roll_mode": self.roll_mode.get(),
            "crit_range": self.crit_range.get(),
            "power_attack": self.power_attack.get(),
            "damage_dice_count": self.damage_dice_count.get(),
            "damage_die_sides": self.damage_die_sides.get(),
            "damage_bonus": self.damage_bonus.get(),
            "manual_hits": self.manual_hits.get(),
            "manual_hit_count": self.manual_hit_count.get(),
            "manual_critical_count": self.manual_critical_count.get(),
        }

    def show_onboarding(self, on_seen: Callable[[], None]) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("欢迎使用快速计算")
        dialog.configure(bg=self.CARD)
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._close_onboarding(dialog, on_seen))
        tk.Label(dialog, text="三步完成一次攻击", bg=self.CARD, fg=self.GOLD, font=(self.family, 18, "bold")).pack(padx=34, pady=(24, 12))
        tk.Label(
            dialog,
            text="① 填写目标 AC\n\n② 填写命中加值、次数和伤害骰\n\n③ 点击“立即结算”查看命中和总伤害",
            justify=tk.LEFT,
            bg=self.CARD,
            fg=self.TEXT,
            font=(self.family, 12),
        ).pack(anchor="w", padx=42, pady=8)
        tk.Label(dialog, text="页面已经填好一个长剑示例。", bg=self.CARD, fg=self.SUB, font=(self.family, 10)).pack(pady=8)
        buttons = tk.Frame(dialog, bg=self.CARD)
        buttons.pack(pady=(8, 24))
        ttk.Button(
            buttons,
            text="使用示例值试一次",
            command=lambda: self._try_example(dialog, on_seen),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            buttons,
            text="开始填写",
            command=lambda: self._close_onboarding(dialog, on_seen),
        ).pack(side=tk.LEFT, padx=4)
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_rootx() + (self.winfo_toplevel().winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_toplevel().winfo_rooty() + (self.winfo_toplevel().winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _try_example(self, dialog: tk.Toplevel, on_seen: Callable[[], None]) -> None:
        self.reset_defaults()
        self._close_onboarding(dialog, on_seen)
        self.run()

    @staticmethod
    def _close_onboarding(dialog: tk.Toplevel, on_seen: Callable[[], None]) -> None:
        on_seen()
        dialog.grab_release()
        dialog.destroy()
