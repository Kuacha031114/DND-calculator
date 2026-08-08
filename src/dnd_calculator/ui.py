"""池中社 DND 战斗计算器 v3 Tkinter 界面。"""

from __future__ import annotations

from dataclasses import replace
import platform
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any
from uuid import uuid4

from .config import ConfigStore
from .engine import RulesEngine, RulesError, format_d20_rolls
from .models import (
    STANDARD_ABILITIES,
    STANDARD_DAMAGE_TYPES,
    AttackGroup,
    AutoEffect,
    DamageComponent,
    DamageReduction,
    DiceModifier,
    DiceTerm,
    RerollPolicy,
    ResolutionMode,
    RollMode,
    SaveEffect,
    SaveOutcome,
    Target,
)
from .presets import (
    PRESET_NAMES,
    SAVE_PRESETS,
    apply_attack_preset,
    brutal_critical,
    divine_smite,
    savage_attacks,
    sneak_attack,
)
from .quick import QuickAttackRequest
from .quick_ui import QuickAttackPage


MODE_LABELS = {
    ResolutionMode.ATTACK.value: "攻击检定",
    ResolutionMode.SAVE.value: "豁免检定",
    ResolutionMode.AUTO.value: "自动伤害",
}
LABEL_MODES = {label: mode for mode, label in MODE_LABELS.items()}


class Theme:
    BG = "#e8dcc0"
    CARD = "#f5ecd6"
    INPUT = "#fbf6e8"
    BORDER = "#b89968"
    TEXT = "#3a2c1a"
    SUB = "#7d6a4d"
    GOLD = "#8a6d3b"
    RED = "#9c3b2e"
    GREEN = "#486b45"

    @staticmethod
    def fonts() -> tuple[str, str]:
        system = platform.system()
        if system == "Windows":
            return "Microsoft YaHei UI", "Consolas"
        if system == "Darwin":
            return "PingFang SC", "Menlo"
        return "Noto Sans CJK SC", "DejaVu Sans Mono"


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def default_target(index: int = 1) -> dict[str, Any]:
    return {
        "id": _identifier("target"),
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


def default_entry(index: int = 1) -> dict[str, Any]:
    return {
        "id": _identifier("entry"),
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


def normalize_entry(entry: dict[str, Any], index: int = 1) -> dict[str, Any]:
    """为旧 v3 条目补齐新增的可选字段，并保留原数据。"""
    return {**default_entry(index), **entry}


def entry_display_values(entry: dict[str, Any], targets: list[dict[str, Any]]) -> tuple[str, str, str]:
    """生成高级工作台列表的中文摘要。"""
    target = next((item for item in targets if item["id"] == entry.get("target_id")), None)
    uses_all_targets = entry.get("mode") in (ResolutionMode.SAVE.value, ResolutionMode.AUTO.value) and entry.get("all_targets")
    target_name = "全部目标" if uses_all_targets else (target["name"] if target else "未指定")
    return entry["name"], MODE_LABELS.get(entry["mode"], entry["mode"]), target_name


class CalculatorApp:
    def __init__(self, root: tk.Tk, config_store: ConfigStore | None = None):
        self.root = root
        self.store = config_store or ConfigStore()
        self.engine = RulesEngine()
        self.sessions = []
        self.attack_session = None
        self.rider_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        self.die_vars: dict[tuple[str, str, int], tk.BooleanVar] = {}
        self._loading = False
        self._stale = False
        self._autosave_after_id = None

        loaded = self.store.load()
        data = loaded.data
        self.targets = data.get("targets") or [default_target()]
        loaded_entries = data.get("entries") or [default_entry()]
        self.entries = [
            normalize_entry(entry, index + 1)
            for index, entry in enumerate(loaded_entries)
        ]
        self.custom_presets = data.get("custom_presets") or {}
        self.quick_config = data.get("quick") or {}
        self.onboarding_seen = bool(data.get("onboarding_seen", False))
        self.help_expanded = bool(data.get("help_expanded", False))
        if not self.entries[0].get("target_id"):
            self.entries[0]["target_id"] = self.targets[0]["id"]
        self.current_target_id = self.targets[0]["id"]
        self.current_entry_id = self.entries[0]["id"]

        self._configure_root(data)
        self._build_styles()
        self._build_ui()
        self._refresh_targets(select_id=self.current_target_id)
        self._refresh_entries(select_id=self.current_entry_id)
        self._load_target(self.current_target_id)
        self._load_entry(self.current_entry_id)
        self.show_quick()
        if self.help_expanded:
            self.quick_page.toggle_help()
        if not self.onboarding_seen:
            self.root.after(350, lambda: self.quick_page.show_onboarding(self._mark_onboarding_seen))
        if loaded.warning:
            self.root.after(100, lambda: messagebox.showwarning("配置恢复", loaded.warning))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _configure_root(self, data: dict[str, Any]) -> None:
        self.root.title("池中社 DND 战斗计算器 v3.1.1")
        self.root.configure(bg=Theme.BG)
        geometry = data.get("window", {}).get("geometry", "1180x780")
        self.root.geometry(geometry)
        self.root.minsize(880, 620)

    def _build_styles(self) -> None:
        family, mono = Theme.fonts()
        self.family = family
        self.mono = mono
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=Theme.CARD)
        style.configure("TLabel", background=Theme.CARD, foreground=Theme.TEXT, font=(family, 10))
        style.configure("TLabelframe", background=Theme.CARD, bordercolor=Theme.BORDER)
        style.configure("TLabelframe.Label", background=Theme.CARD, foreground=Theme.GOLD, font=(family, 11, "bold"))
        style.configure("TButton", font=(family, 10), padding=5)
        style.configure("Accent.TButton", background=Theme.RED, foreground="white", font=(family, 11, "bold"))
        style.configure("Treeview", background=Theme.INPUT, fieldbackground=Theme.INPUT, rowheight=25, font=(family, 10))
        style.configure("Treeview.Heading", font=(family, 10, "bold"))
        style.configure("TNotebook", background=Theme.BG)
        style.configure("TNotebook.Tab", padding=(14, 7), font=(family, 10, "bold"))

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=Theme.GOLD)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="⚔ 池中社 DND 战斗计算器 v3.1.1 · 2014 规则",
            bg=Theme.GOLD,
            fg="white",
            font=(self.family, 17, "bold"),
            pady=10,
        ).pack(side=tk.LEFT, padx=18)
        nav = tk.Frame(header, bg=Theme.GOLD)
        nav.pack(side=tk.RIGHT, padx=14, pady=7)
        self.quick_nav = tk.Button(
            nav, text="快速计算", command=self.show_quick, bg=Theme.CARD, fg=Theme.TEXT,
            relief=tk.FLAT, font=(self.family, 10, "bold"), padx=14, pady=5,
        )
        self.quick_nav.pack(side=tk.LEFT, padx=3)
        self.advanced_nav = tk.Button(
            nav, text="高级工作台", command=self.show_advanced, bg=Theme.GOLD, fg="white",
            relief=tk.FLAT, font=(self.family, 10, "bold"), padx=14, pady=5,
        )
        self.advanced_nav.pack(side=tk.LEFT, padx=3)

        self.content = tk.Frame(self.root, bg=Theme.BG)
        self.content.pack(fill=tk.BOTH, expand=True)
        self.quick_container = tk.Frame(self.content, bg=Theme.BG)
        self.advanced_container = tk.Frame(self.content, bg=Theme.BG)
        self.quick_page = QuickAttackPage(
            self.quick_container,
            family=self.family,
            mono=self.mono,
            data=self.quick_config,
            engine=self.engine,
            on_advanced=self.show_advanced,
            on_import_advanced=self.import_quick_to_advanced,
        )
        self.quick_page.pack(fill=tk.BOTH, expand=True)
        self._build_advanced_workspace(self.advanced_container)

        footer = tk.Frame(self.root, bg="#c9b98a")
        footer.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(footer, textvariable=self.status_var, bg="#c9b98a", fg=Theme.SUB, anchor="w").pack(
            fill=tk.X, padx=12, pady=4
        )

    def _build_advanced_workspace(self, parent: tk.Frame) -> None:
        guide = tk.Frame(parent, bg=Theme.CARD, highlightbackground=Theme.BORDER, highlightthickness=1)
        guide.pack(fill=tk.X, padx=10, pady=(10, 0))
        heading = tk.Frame(guide, bg=Theme.CARD)
        heading.pack(fill=tk.X, padx=12, pady=(8, 5))
        tk.Label(
            heading, text="高级工作台", bg=Theme.CARD, fg=Theme.GOLD,
            font=(self.family, 15, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            heading, text="用于多目标、豁免法术、偷袭、至圣斩和伤害抗性",
            bg=Theme.CARD, fg=Theme.SUB, font=(self.family, 10),
        ).pack(side=tk.LEFT, padx=12, pady=(3, 0))
        ttk.Button(heading, text="返回快速计算", command=self.show_quick).pack(side=tk.RIGHT)
        ttk.Button(
            heading, text="工作台说明", command=lambda: messagebox.showinfo(
                "高级工作台使用说明",
                "先在左侧选择目标和攻击/法术，再填写当前条目的数值。\n\n"
                "右侧先点击“投掷检定 / 结算法术”。攻击命中后，如需偷袭或至圣斩，"
                "到“命中后附加”页选择具体命中，再点击“结算攻击伤害”。\n\n"
                "没有用到的高级规则保持未勾选或 0 即可。",
                parent=self.root,
            )
        ).pack(side=tk.RIGHT, padx=6)

        flow = tk.Frame(guide, bg=Theme.CARD)
        flow.pack(fill=tk.X, padx=12, pady=(0, 8))
        for number, label in (("1", "选择目标"), ("2", "配置攻击或法术"), ("3", "投掷检定"), ("4", "选择附加伤害"), ("5", "查看最终结果")):
            item = tk.Frame(flow, bg=Theme.INPUT, highlightbackground=Theme.BORDER, highlightthickness=1)
            item.pack(side=tk.LEFT, padx=(0, 7))
            tk.Label(item, text=number, bg=Theme.GOLD, fg="white", width=2, font=(self.family, 10, "bold")).pack(side=tk.LEFT)
            tk.Label(item, text=label, bg=Theme.INPUT, fg=Theme.TEXT, font=(self.family, 9)).pack(side=tk.LEFT, padx=7, pady=3)

        paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, sashwidth=6, bg=Theme.BORDER)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        left = tk.Frame(paned, bg=Theme.BG)
        right = tk.Frame(paned, bg=Theme.BG)
        paned.add(left, minsize=500, stretch="always")
        paned.add(right, minsize=400, stretch="always")

        notebook = ttk.Notebook(left)
        self.advanced_notebook = notebook
        notebook.pack(fill=tk.BOTH, expand=True)
        basic = ttk.Frame(notebook, padding=8)
        advanced = ttk.Frame(notebook, padding=8)
        notebook.add(basic, text="① 基础配置")
        notebook.add(advanced, text="② 高级选项")
        self._build_basic(basic)
        self._build_advanced(advanced)
        self._build_results(right)

    def show_quick(self) -> None:
        self.advanced_container.pack_forget()
        self.quick_container.pack(fill=tk.BOTH, expand=True)
        self.quick_nav.configure(bg=Theme.CARD, fg=Theme.TEXT)
        self.advanced_nav.configure(bg=Theme.GOLD, fg="white")
        if hasattr(self, "status_var"):
            self.status_var.set("快速计算：填写常用数值后点击“立即结算”")

    def show_advanced(self) -> None:
        self.quick_container.pack_forget()
        self.advanced_container.pack(fill=tk.BOTH, expand=True)
        self.quick_nav.configure(bg=Theme.GOLD, fg="white")
        self.advanced_nav.configure(bg=Theme.CARD, fg=Theme.TEXT)
        self.status_var.set("高级工作台：适用于多目标、豁免法术和命中后附加伤害")

    def _mark_onboarding_seen(self) -> None:
        self.onboarding_seen = True

    def _build_basic(self, parent: ttk.Frame) -> None:
        target_box = ttk.LabelFrame(parent, text="① 选择并编辑目标", padding=8)
        target_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            target_box,
            text="每个目标可以拥有独立 AC、豁免和伤害防御；详细防御在“高级选项”中填写。",
            foreground=Theme.SUB,
        ).pack(anchor="w", pady=(0, 5))
        self.target_tree = ttk.Treeview(target_box, columns=("name", "ac"), show="headings", height=2)
        self.target_tree.heading("name", text="目标名称")
        self.target_tree.heading("ac", text="AC")
        self.target_tree.column("name", width=250)
        self.target_tree.column("ac", width=55, anchor="center")
        self.target_tree.pack(fill=tk.X)
        self.target_tree.bind("<<TreeviewSelect>>", self._on_target_select)

        self.target_name = tk.StringVar()
        self.target_ac = tk.StringVar()
        row = ttk.Frame(target_box)
        row.pack(fill=tk.X, pady=5)
        for text, command in (("＋ 添加目标", self.add_target), ("复制当前目标", self.duplicate_target), ("删除当前目标", self.delete_target)):
            ttk.Button(row, text=text, command=command).pack(side=tk.LEFT, padx=2)
        self._field(row, "当前名称", self.target_name, width=13).pack(side=tk.RIGHT, padx=3)
        self._field(row, "当前 AC", self.target_ac, width=5).pack(side=tk.RIGHT, padx=3)

        entry_box = ttk.LabelFrame(parent, text="② 配置攻击或法术", padding=8)
        entry_box.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            entry_box,
            text="列表中的每一行代表一组攻击、一个豁免法术或一次自动伤害。",
            foreground=Theme.SUB,
        ).pack(anchor="w", pady=(0, 5))
        self.entry_tree = ttk.Treeview(entry_box, columns=("name", "mode", "target"), show="headings", height=3)
        self.entry_tree.heading("name", text="名称")
        self.entry_tree.heading("mode", text="模式")
        self.entry_tree.heading("target", text="目标")
        self.entry_tree.column("name", width=145)
        self.entry_tree.column("mode", width=80, anchor="center")
        self.entry_tree.column("target", width=110)
        self.entry_tree.pack(fill=tk.X)
        self.entry_tree.bind("<<TreeviewSelect>>", self._on_entry_select)
        buttons = ttk.Frame(entry_box)
        buttons.pack(fill=tk.X, pady=5)
        for text, command in (
            ("＋ 添加攻击或法术", self.add_entry), ("复制当前项", self.duplicate_entry), ("删除当前项", self.delete_entry),
            ("上移", lambda: self.move_entry(-1)), ("下移", lambda: self.move_entry(1)),
        ):
            ttk.Button(buttons, text=text, command=command).pack(side=tk.LEFT, padx=2)

        self.entry_name = tk.StringVar()
        self.entry_mode = tk.StringVar()
        self.entry_target = tk.StringVar()
        self.entry_count = tk.StringVar()
        self.attack_bonus = tk.StringVar()
        self.manual_hits = tk.BooleanVar()
        self.manual_hit_count = tk.StringVar()
        self.manual_critical_count = tk.StringVar()
        self.save_dc = tk.StringVar()
        self.save_ability = tk.StringVar()
        self.save_outcome = tk.StringVar()
        self.all_targets = tk.BooleanVar()
        self.damage_name = tk.StringVar()
        self.dice_count = tk.StringVar()
        self.dice_sides = tk.StringVar()
        self.flat_bonus = tk.StringVar()
        self.damage_type = tk.StringVar()

        editor = ttk.LabelFrame(entry_box, text="③ 编辑当前选中内容（自动保存）", padding=7)
        editor.pack(fill=tk.X, pady=(2, 0))
        common = ttk.Frame(editor)
        common.pack(fill=tk.X)
        self._grid_label(common, "名称", 0, 0)
        ttk.Entry(common, textvariable=self.entry_name, width=15).grid(row=0, column=1, sticky="ew", padx=3, pady=2)
        self._grid_label(common, "结算方式", 0, 2)
        ttk.Combobox(
            common,
            textvariable=self.entry_mode,
            values=tuple(MODE_LABELS.values()),
            state="readonly",
            width=9,
        ).grid(row=0, column=3, sticky="ew", padx=3)
        self._grid_label(common, "作用目标", 1, 0)
        self.target_combo = ttk.Combobox(common, textvariable=self.entry_target, state="readonly", width=15)
        self.target_combo.grid(row=1, column=1, sticky="ew", padx=3, pady=2)
        self.all_targets_check = ttk.Checkbutton(common, text="同时作用于全部目标", variable=self.all_targets)
        self.all_targets_check.grid(row=1, column=2, columnspan=2, sticky="w")
        common.columnconfigure(1, weight=1)
        common.columnconfigure(3, weight=1)

        self.mode_hint = tk.StringVar(value="")
        ttk.Label(editor, textvariable=self.mode_hint, foreground=Theme.GOLD).pack(anchor="w", pady=(5, 2))
        self.mode_fields = ttk.Frame(editor)
        self.mode_fields.pack(fill=tk.X)

        self.attack_fields = ttk.Frame(self.mode_fields)
        self._grid_label(self.attack_fields, "攻击次数", 0, 0)
        ttk.Entry(self.attack_fields, textvariable=self.entry_count, width=7).grid(row=0, column=1, sticky="w", padx=3)
        self._grid_label(self.attack_fields, "命中加值", 0, 2)
        ttk.Entry(self.attack_fields, textvariable=self.attack_bonus, width=7).grid(row=0, column=3, sticky="w", padx=3)
        ttk.Checkbutton(
            self.attack_fields,
            text="AC 未知，手动指定命中",
            variable=self.manual_hits,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=3, pady=(7, 2))
        self._grid_label(self.attack_fields, "命中次数", 1, 2)
        ttk.Entry(self.attack_fields, textvariable=self.manual_hit_count, width=7).grid(row=1, column=3, sticky="w", padx=3, pady=(7, 2))
        self._grid_label(self.attack_fields, "其中重击", 1, 4)
        ttk.Entry(self.attack_fields, textvariable=self.manual_critical_count, width=7).grid(row=1, column=5, sticky="w", padx=3, pady=(7, 2))
        ttk.Label(
            self.attack_fields,
            text="启用后不投 d20，AC、命中加值、优势或劣势、附加检定骰和重击下限不参与判定。",
            foreground=Theme.SUB,
        ).grid(row=2, column=0, columnspan=6, sticky="w", padx=3, pady=(1, 3))

        self.save_fields = ttk.Frame(self.mode_fields)
        self._grid_label(self.save_fields, "豁免 DC", 0, 0)
        ttk.Entry(self.save_fields, textvariable=self.save_dc, width=7).grid(row=0, column=1, sticky="w", padx=3)
        self._grid_label(self.save_fields, "豁免属性", 0, 2)
        ttk.Combobox(self.save_fields, textvariable=self.save_ability, values=STANDARD_ABILITIES, state="readonly", width=7).grid(
            row=0, column=3, sticky="w", padx=3
        )
        self._grid_label(self.save_fields, "豁免成功时", 0, 4)
        ttk.Combobox(self.save_fields, textvariable=self.save_outcome, values=tuple(SAVE_PRESETS), state="readonly", width=11).grid(
            row=0, column=5, sticky="w", padx=3
        )

        self.auto_fields = ttk.Frame(self.mode_fields)
        ttk.Label(
            self.auto_fields,
            text="自动伤害不投 d20，会直接对所选目标投掷并结算下方伤害。",
            foreground=Theme.SUB,
        ).pack(anchor="w", pady=3)

        damage = ttk.LabelFrame(editor, text="伤害", padding=5)
        damage.pack(fill=tk.X, pady=(6, 0))
        self._grid_label(damage, "名称", 0, 0)
        ttk.Entry(damage, textvariable=self.damage_name, width=13).grid(row=0, column=1, sticky="ew", padx=3)
        self._grid_label(damage, "伤害骰", 0, 2)
        dice_row = ttk.Frame(damage)
        dice_row.grid(row=0, column=3, sticky="w")
        ttk.Entry(dice_row, textvariable=self.dice_count, width=3).pack(side=tk.LEFT)
        ttk.Label(dice_row, text="d").pack(side=tk.LEFT)
        ttk.Entry(dice_row, textvariable=self.dice_sides, width=4).pack(side=tk.LEFT)
        ttk.Label(dice_row, text="+ 伤害加值").pack(side=tk.LEFT, padx=3)
        ttk.Entry(dice_row, textvariable=self.flat_bonus, width=5).pack(side=tk.LEFT)
        self._grid_label(damage, "伤害类型", 0, 4)
        ttk.Combobox(
            damage,
            textvariable=self.damage_type,
            values=STANDARD_DAMAGE_TYPES + ("自定义",),
            state="readonly",
            width=8,
        ).grid(row=0, column=5, sticky="w", padx=3)
        damage.columnconfigure(1, weight=1)

        self.entry_mode.trace_add("write", self._update_entry_mode_visibility)

    def _update_entry_mode_visibility(self, *_args) -> None:
        """只展示当前结算方式真正需要的输入，减少无关字段干扰。"""
        if not hasattr(self, "attack_fields"):
            return
        for frame in (self.attack_fields, self.save_fields, self.auto_fields):
            frame.pack_forget()
        mode = LABEL_MODES.get(self.entry_mode.get(), self.entry_mode.get())
        if mode == ResolutionMode.SAVE.value:
            self.save_fields.pack(fill=tk.X)
            self.all_targets_check.grid()
            self.mode_hint.set("豁免检定：每个目标独立投 d20，并按成功结果结算伤害。")
        elif mode == ResolutionMode.AUTO.value:
            self.auto_fields.pack(fill=tk.X)
            self.all_targets_check.grid()
            self.mode_hint.set("自动伤害：跳过攻击和豁免，直接结算伤害。")
        else:
            self.attack_fields.pack(fill=tk.X)
            self.all_targets_check.grid_remove()
            self.mode_hint.set("攻击检定：按攻击次数逐次投 d20，命中后再结算伤害。")

    def _build_advanced(self, parent: ttk.Frame) -> None:
        self.advantage = tk.StringVar()
        self.disadvantage = tk.StringVar()
        self.crit_range = tk.StringVar()
        self.elven_accuracy = tk.BooleanVar()
        self.halfling_lucky = tk.BooleanVar()
        self.power_attack = tk.BooleanVar()
        self.power_indices = tk.StringVar()
        self.weapon_die = tk.BooleanVar()
        self.magical = tk.BooleanVar()
        self.gwf = tk.BooleanVar()
        self.bless = tk.BooleanVar()
        self.bane = tk.BooleanVar()
        self.preset = tk.StringVar()
        self.rider = tk.StringVar()
        self.rider_dice = tk.StringVar()
        self.rider_sides = tk.StringVar()

        tabs = ttk.Notebook(parent)
        self.advanced_rule_tabs = tabs
        tabs.pack(fill=tk.BOTH, expand=True)
        attack_tab = ttk.Frame(tabs, padding=10)
        rider_tab = ttk.Frame(tabs, padding=10)
        defense_tab = ttk.Frame(tabs, padding=10)
        tabs.add(attack_tab, text="攻击规则")
        tabs.add(rider_tab, text="预设与附加伤害")
        tabs.add(defense_tab, text="目标防御")

        ttk.Label(
            attack_tab,
            text="只填写当前攻击实际用到的规则；来源数为 0、未勾选即表示不启用。",
            foreground=Theme.SUB,
        ).pack(anchor="w", pady=(0, 8))
        d20_box = ttk.LabelFrame(attack_tab, text="d20 与重击", padding=8)
        d20_box.pack(fill=tk.X, pady=(0, 8))
        for column, (text, var) in enumerate((("优势来源数", self.advantage), ("劣势来源数", self.disadvantage), ("重击下限", self.crit_range))):
            self._field(d20_box, text, var, 6).grid(row=0, column=column, padx=5, sticky="w")
        check_grid = ttk.Frame(d20_box)
        check_grid.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for index, (text, var) in enumerate((
            ("精灵精准（三骰取高）", self.elven_accuracy),
            ("半身人幸运（自然 1 重骰一次）", self.halfling_lucky),
            ("祝福术（命中 +1d4）", self.bless),
            ("灾祸术（命中 -1d4）", self.bane),
        )):
            ttk.Checkbutton(check_grid, text=text, variable=var).grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 16), pady=2)

        weapon_box = ttk.LabelFrame(attack_tab, text="武器与 -5/+10", padding=8)
        weapon_box.pack(fill=tk.X)
        option_grid = ttk.Frame(weapon_box)
        option_grid.pack(fill=tk.X)
        for index, (text, var) in enumerate((
            ("主要伤害属于武器骰", self.weapon_die),
            ("伤害视为魔法伤害", self.magical),
            ("启用重武器战斗风格", self.gwf),
            ("本组全部攻击使用 -5/+10", self.power_attack),
        )):
            ttk.Checkbutton(option_grid, text=text, variable=var).grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 16), pady=2)
        index_row = ttk.Frame(weapon_box)
        index_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(index_row, text="仅指定攻击使用 -5/+10").pack(side=tk.LEFT)
        ttk.Entry(index_row, textvariable=self.power_indices, width=14).pack(side=tk.LEFT, padx=6)
        ttk.Label(index_row, text="填写序号，例如 1,3；勾选“全部攻击”时此项忽略", foreground=Theme.SUB).pack(side=tk.LEFT)

        ttk.Label(
            rider_tab,
            text="预设用于快速填充规则；具体等级、武器资格和资源消耗仍由玩家确认。",
            foreground=Theme.SUB,
        ).pack(anchor="w", pady=(0, 8))
        preset_box = ttk.LabelFrame(rider_tab, text="通用攻击预设", padding=8)
        preset_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(preset_box, text="选择预设").grid(row=0, column=0, sticky="w")
        self.preset_combo = ttk.Combobox(preset_box, textvariable=self.preset, values=self._preset_values(), state="readonly", width=25)
        self.preset_combo.grid(row=0, column=1, sticky="w", padx=6)

        rider_box = ttk.LabelFrame(rider_tab, text="命中后附加伤害", padding=8)
        rider_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(rider_box, text="附加效果").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            rider_box,
            textvariable=self.rider,
            values=("无", "偷袭", "至圣斩", "凶蛮攻击", "野蛮重击"),
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(rider_box, text="伤害骰").grid(row=0, column=2, sticky="w", padx=(14, 3))
        rider_dice = ttk.Frame(rider_box)
        rider_dice.grid(row=0, column=3, sticky="w")
        ttk.Entry(rider_dice, textvariable=self.rider_dice, width=3).pack(side=tk.LEFT)
        ttk.Label(rider_dice, text="d").pack(side=tk.LEFT)
        ttk.Entry(rider_dice, textvariable=self.rider_sides, width=4).pack(side=tk.LEFT)
        ttk.Label(
            rider_box,
            text="偷袭、至圣斩会在投掷检定后选择具体命中；重击时由规则引擎自动增加合格骰子。",
            foreground=Theme.SUB,
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        custom_box = ttk.LabelFrame(rider_tab, text="自定义预设", padding=8)
        custom_box.pack(fill=tk.X)
        ttk.Label(custom_box, text="把当前条目的设置保存下来，供之后的攻击快速复用。", foreground=Theme.SUB).pack(anchor="w", pady=(0, 6))
        preset_buttons = ttk.Frame(custom_box)
        preset_buttons.pack(anchor="w")
        ttk.Button(preset_buttons, text="保存为自定义预设", command=self.save_custom_preset).pack(side=tk.LEFT)
        ttk.Button(preset_buttons, text="载入自定义预设", command=self.load_custom_preset).pack(side=tk.LEFT, padx=4)
        ttk.Button(preset_buttons, text="删除自定义预设", command=self.delete_custom_preset).pack(side=tk.LEFT)

        self.defense_target_text = tk.StringVar(value="当前目标")
        ttk.Label(defense_tab, textvariable=self.defense_target_text, foreground=Theme.GOLD, font=(self.family, 11, "bold")).pack(anchor="w")
        ttk.Label(
            defense_tab,
            text="这些数值属于左侧当前选中的目标，不属于攻击或法术条目。伤害类型使用逗号分隔。",
            foreground=Theme.SUB,
        ).pack(anchor="w", pady=(2, 8))
        defense = ttk.LabelFrame(defense_tab, text="六项豁免加值", padding=8)
        defense.pack(fill=tk.X, pady=(0, 8))
        self.save_vars = {ability: tk.StringVar() for ability in STANDARD_ABILITIES}
        for index, ability in enumerate(STANDARD_ABILITIES):
            self._field(defense, ability, self.save_vars[ability], 6).grid(
                row=index // 3, column=index % 3, padx=4, pady=2, sticky="w"
            )
        self.resistances = tk.StringVar()
        self.vulnerabilities = tk.StringVar()
        self.immunities = tk.StringVar()
        self.nonmagical_resistances = tk.StringVar()
        self.crit_immune = tk.BooleanVar()
        self.fixed_reduction = tk.StringVar()
        damage_defense = ttk.LabelFrame(defense_tab, text="伤害防御", padding=8)
        damage_defense.pack(fill=tk.X)
        for row_index, (text, var) in enumerate(
            (("抗性", self.resistances), ("易伤", self.vulnerabilities), ("免疫", self.immunities),
             ("非魔法武器抗性", self.nonmagical_resistances))
        ):
            ttk.Label(damage_defense, text=text).grid(row=row_index, column=0, sticky="w", pady=3)
            ttk.Entry(damage_defense, textvariable=var, width=30).grid(row=row_index, column=1, sticky="ew", padx=6, pady=3)
        ttk.Checkbutton(damage_defense, text="免疫重击额外骰（攻击仍可命中）", variable=self.crit_immune).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 2))
        self._field(damage_defense, "每次伤害固定减免", self.fixed_reduction, 7).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))
        damage_defense.columnconfigure(1, weight=1)
        ttk.Label(parent, text="所有高级选项都会自动保存。", foreground=Theme.SUB).pack(anchor="e", pady=7)

    def _build_results(self, parent: tk.Frame) -> None:
        action_box = tk.Frame(parent, bg=Theme.CARD, highlightbackground=Theme.BORDER, highlightthickness=1)
        action_box.pack(fill=tk.X, pady=(0, 7))
        tk.Label(
            action_box, text="结算流程", bg=Theme.CARD, fg=Theme.GOLD,
            font=(self.family, 13, "bold"),
        ).pack(anchor="w", padx=10, pady=(8, 2))
        self.result_stage_var = tk.StringVar(value="准备就绪：完成左侧配置后，从第 1 步开始。")
        tk.Label(
            action_box, textvariable=self.result_stage_var, bg=Theme.CARD, fg=Theme.SUB,
            justify=tk.LEFT, anchor="w", wraplength=520, font=(self.family, 9),
        ).pack(fill=tk.X, padx=10, pady=(0, 6))
        toolbar = tk.Frame(action_box, bg=Theme.CARD)
        toolbar.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(
            toolbar, text="① 投掷检定 / 结算法术", style="Accent.TButton", command=self.run_resolution,
        ).pack(side=tk.LEFT)
        self.damage_button = ttk.Button(
            toolbar, text="③ 结算攻击伤害", command=self.roll_attack_damage, state=tk.DISABLED,
        )
        self.damage_button.pack(side=tk.LEFT, padx=6)

        self.result_tabs = ttk.Notebook(parent)
        self.result_tabs.pack(fill=tk.BOTH, expand=True)
        result_tab = ttk.Frame(self.result_tabs, padding=7)
        self.rider_tab = ttk.Frame(self.result_tabs, padding=8)
        self.reroll_tab = ttk.Frame(self.result_tabs, padding=8)
        self.result_tabs.add(result_tab, text="结算结果")
        self.result_tabs.add(self.rider_tab, text="② 命中后附加")
        self.result_tabs.add(self.reroll_tab, text="可选：手动重骰")

        self.result_text = ScrolledText(
            result_tab,
            font=(self.mono, 10),
            bg=Theme.CARD,
            fg=Theme.TEXT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            height=20,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.bind("<Key>", lambda _event: "break")

        ttk.Label(
            self.rider_tab,
            text="只有命中的攻击可以选择偷袭、至圣斩等附加伤害。选择后回到上方点击“③ 结算攻击伤害”。",
            foreground=Theme.SUB,
            wraplength=440,
        ).pack(anchor="w", pady=(0, 8))
        self.rider_frame = ttk.LabelFrame(self.rider_tab, text="可选择的命中", padding=8)
        self.rider_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(self.rider_frame, text="投掷检定后，这里会列出可以附加伤害的命中。").pack(anchor="w")

        ttk.Label(
            self.reroll_tab,
            text="这是通用手动重骰工具。勾选具体骰子后应用重骰，新结果必须接受。",
            foreground=Theme.SUB,
            wraplength=440,
        ).pack(anchor="w", pady=(0, 8))
        self.dice_frame = ttk.LabelFrame(self.reroll_tab, text="已投出的伤害骰", padding=8)
        self.dice_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        ttk.Label(self.dice_frame, text="结算伤害后，这里会列出可选择的骰子。").pack(anchor="w")
        self.reroll_button = ttk.Button(
            self.reroll_tab, text="应用所选重骰", command=self.reroll_selected, state=tk.DISABLED,
        )
        self.reroll_button.pack(anchor="e")
        self._set_result("尚未结算。请先在左侧选择目标和攻击/法术，然后点击“① 投掷检定 / 结算法术”。")

    def _field(self, parent, label: str, variable: tk.Variable, width: int = 8) -> ttk.Frame:
        frame = ttk.Frame(parent)
        ttk.Label(frame, text=label).pack(anchor="w")
        ttk.Entry(frame, textvariable=variable, width=width).pack(anchor="w")
        return frame

    @staticmethod
    def _grid_label(parent, text: str, row: int, column: int) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=column, sticky="w", padx=3, pady=2)

    def _all_vars(self):
        variables = [
            self.target_name, self.target_ac, self.entry_name, self.entry_mode, self.entry_target,
            self.entry_count, self.attack_bonus, self.save_dc, self.save_ability, self.save_outcome,
            self.manual_hits, self.manual_hit_count, self.manual_critical_count,
            self.all_targets, self.damage_name, self.dice_count, self.dice_sides, self.flat_bonus,
            self.damage_type, self.advantage, self.disadvantage, self.crit_range, self.elven_accuracy,
            self.halfling_lucky, self.power_attack, self.weapon_die, self.magical, self.gwf, self.bless,
            self.power_indices, self.bane, self.preset, self.rider, self.rider_dice, self.rider_sides, self.resistances,
            self.vulnerabilities, self.immunities, self.nonmagical_resistances, self.crit_immune,
            self.fixed_reduction,
        ]
        variables.extend(self.save_vars.values())
        return variables

    def _attach_traces(self) -> None:
        for variable in self._all_vars():
            variable.trace_add("write", self._schedule_advanced_save)

    def _schedule_advanced_save(self, *_args) -> None:
        if self._loading:
            return
        self._mark_stale()
        if self._autosave_after_id is not None:
            self.root.after_cancel(self._autosave_after_id)
        self._autosave_after_id = self.root.after(300, self._autosave_editors)

    def _autosave_editors(self) -> None:
        self._autosave_after_id = None
        if self._loading:
            return
        self.apply_editors(quiet=True)

    def _mark_stale(self, *_args) -> None:
        if self._loading or not self.sessions:
            return
        self._stale = True
        self.status_var.set("⚠ 输入已改变，旧结果已标记过期，请重新投掷检定")
        if hasattr(self, "result_stage_var"):
            self.result_stage_var.set("设置已改变：当前结果已过期，请重新执行第 1 步。")

    def _refresh_targets(self, select_id: str | None = None) -> None:
        self.target_tree.delete(*self.target_tree.get_children())
        for target in self.targets:
            self.target_tree.insert("", tk.END, iid=target["id"], values=(target["name"], target["ac"]))
        names = [target["name"] for target in self.targets]
        self.target_combo.configure(values=names)
        if select_id and self.target_tree.exists(select_id):
            self.target_tree.selection_set(select_id)

    def _refresh_entries(self, select_id: str | None = None) -> None:
        self.entry_tree.delete(*self.entry_tree.get_children())
        for entry in self.entries:
            self.entry_tree.insert(
                "", tk.END, iid=entry["id"],
                values=entry_display_values(entry, self.targets),
            )
        if select_id and self.entry_tree.exists(select_id):
            self.entry_tree.selection_set(select_id)

    def _preset_values(self) -> tuple[str, ...]:
        return PRESET_NAMES + tuple(f"自定义：{name}" for name in sorted(self.custom_presets))

    def save_custom_preset(self) -> None:
        self.apply_editors()
        name = simpledialog.askstring("保存自定义预设", "预设名称：", parent=self.root)
        if not name or not name.strip():
            return
        entry = next(item for item in self.entries if item["id"] == self.current_entry_id)
        excluded = {"id", "name", "target_id", "preset"}
        self.custom_presets[name.strip()] = {key: value for key, value in entry.items() if key not in excluded}
        self.preset_combo.configure(values=self._preset_values())
        self.preset.set(f"自定义：{name.strip()}")
        self.status_var.set(f"已保存自定义预设：{name.strip()}")

    def load_custom_preset(self) -> None:
        value = self.preset.get()
        if not value.startswith("自定义："):
            messagebox.showinfo("载入预设", "请先在攻击预设中选择一个自定义预设。")
            return
        name = value.removeprefix("自定义：")
        if name not in self.custom_presets:
            messagebox.showerror("载入预设", "找不到该自定义预设。")
            return
        entry = next(item for item in self.entries if item["id"] == self.current_entry_id)
        entry.update(self.custom_presets[name])
        entry["preset"] = "无"
        self._load_entry(entry["id"])
        self._mark_stale()
        self.status_var.set(f"已载入自定义预设：{name}")

    def delete_custom_preset(self) -> None:
        value = self.preset.get()
        if not value.startswith("自定义："):
            messagebox.showinfo("删除预设", "请先选择一个自定义预设。")
            return
        name = value.removeprefix("自定义：")
        if name in self.custom_presets:
            del self.custom_presets[name]
        self.preset.set("无")
        self.preset_combo.configure(values=self._preset_values())
        self.status_var.set(f"已删除自定义预设：{name}")

    def _on_target_select(self, _event=None) -> None:
        selected = self.target_tree.selection()
        if selected and selected[0] != self.current_target_id:
            self.apply_editors(quiet=True)
            self._load_target(selected[0])

    def _on_entry_select(self, _event=None) -> None:
        selected = self.entry_tree.selection()
        if selected and selected[0] != self.current_entry_id:
            self.apply_editors(quiet=True)
            self._load_entry(selected[0])

    def _load_target(self, target_id: str) -> None:
        target = next(item for item in self.targets if item["id"] == target_id)
        self.current_target_id = target_id
        self._loading = True
        self.target_name.set(target["name"])
        self.target_ac.set(target["ac"])
        for ability in STANDARD_ABILITIES:
            self.save_vars[ability].set(target.get("saves", {}).get(ability, "0"))
        self.resistances.set(target.get("resistances", ""))
        self.vulnerabilities.set(target.get("vulnerabilities", ""))
        self.immunities.set(target.get("immunities", ""))
        self.nonmagical_resistances.set(target.get("nonmagical_resistances", ""))
        self.crit_immune.set(target.get("crit_immune", False))
        self.fixed_reduction.set(target.get("fixed_reduction", "0"))
        self.defense_target_text.set(f"当前目标：{target['name']}")
        self._loading = False

    def _load_entry(self, entry_id: str) -> None:
        entry = next(item for item in self.entries if item["id"] == entry_id)
        self.current_entry_id = entry_id
        target = next((item for item in self.targets if item["id"] == entry.get("target_id")), self.targets[0])
        mapping = (
            (self.entry_name, entry["name"]), (self.entry_mode, MODE_LABELS.get(entry["mode"], entry["mode"])), (self.entry_target, target["name"]),
            (self.entry_count, entry["count"]), (self.attack_bonus, entry["attack_bonus"]), (self.save_dc, entry["dc"]),
            (self.manual_hits, entry.get("manual_hits", False)),
            (self.manual_hit_count, entry.get("manual_hit_count", "1")),
            (self.manual_critical_count, entry.get("manual_critical_count", "0")),
            (self.save_ability, entry["save_ability"]), (self.save_outcome, entry["save_outcome"]),
            (self.all_targets, entry["all_targets"]), (self.damage_name, entry["damage_name"]),
            (self.dice_count, entry["dice_count"]), (self.dice_sides, entry["dice_sides"]),
            (self.flat_bonus, entry["flat_bonus"]), (self.damage_type, entry["damage_type"]),
            (self.advantage, entry["advantage"]), (self.disadvantage, entry["disadvantage"]),
            (self.crit_range, entry["crit_range"]), (self.elven_accuracy, entry["elven_accuracy"]),
            (self.halfling_lucky, entry["halfling_lucky"]), (self.power_attack, entry["power_attack"]),
            (self.power_indices, entry.get("power_indices", "")),
            (self.weapon_die, entry["weapon_die"]), (self.magical, entry["magical"]),
            (self.gwf, entry["great_weapon_fighting"]), (self.bless, entry["bless"]),
            (self.bane, entry["bane"]), (self.preset, entry["preset"]), (self.rider, entry["rider"]),
            (self.rider_dice, entry["rider_dice"]), (self.rider_sides, entry["rider_sides"]),
        )
        self._loading = True
        for variable, value in mapping:
            variable.set(value)
        self._loading = False
        self._update_entry_mode_visibility()

    def apply_editors(self, quiet: bool = False) -> None:
        entry = next(item for item in self.entries if item["id"] == self.current_entry_id)
        target_match = next(
            (item for item in self.targets if item["name"] == self.entry_target.get()),
            next((item for item in self.targets if item["id"] == entry.get("target_id")), self.targets[0]),
        )
        target = next(item for item in self.targets if item["id"] == self.current_target_id)
        target.update(
            name=self.target_name.get().strip() or "未命名目标",
            ac=self.target_ac.get(),
            saves={ability: self.save_vars[ability].get() for ability in STANDARD_ABILITIES},
            resistances=self.resistances.get(), vulnerabilities=self.vulnerabilities.get(),
            immunities=self.immunities.get(), nonmagical_resistances=self.nonmagical_resistances.get(),
            crit_immune=self.crit_immune.get(), fixed_reduction=self.fixed_reduction.get(),
        )
        entry.update(
            name=self.entry_name.get().strip() or "未命名条目", mode=LABEL_MODES.get(self.entry_mode.get(), self.entry_mode.get()), target_id=target_match["id"],
            all_targets=self.all_targets.get(), count=self.entry_count.get(), attack_bonus=self.attack_bonus.get(),
            manual_hits=self.manual_hits.get(), manual_hit_count=self.manual_hit_count.get(),
            manual_critical_count=self.manual_critical_count.get(),
            dc=self.save_dc.get(), save_ability=self.save_ability.get(), save_outcome=self.save_outcome.get(),
            damage_name=self.damage_name.get(), dice_count=self.dice_count.get(), dice_sides=self.dice_sides.get(),
            flat_bonus=self.flat_bonus.get(), damage_type=self.damage_type.get(), advantage=self.advantage.get(),
            disadvantage=self.disadvantage.get(), crit_range=self.crit_range.get(), elven_accuracy=self.elven_accuracy.get(),
            halfling_lucky=self.halfling_lucky.get(), power_attack=self.power_attack.get(), weapon_die=self.weapon_die.get(),
            power_indices=self.power_indices.get(),
            magical=self.magical.get(), great_weapon_fighting=self.gwf.get(), bless=self.bless.get(), bane=self.bane.get(),
            preset=self.preset.get(), rider=self.rider.get(), rider_dice=self.rider_dice.get(), rider_sides=self.rider_sides.get(),
        )
        if self.target_tree.exists(target["id"]):
            self.target_tree.item(target["id"], values=(target["name"], target["ac"]))
        for item in self.entries:
            if self.entry_tree.exists(item["id"]):
                self.entry_tree.item(item["id"], values=entry_display_values(item, self.targets))
        self.target_combo.configure(values=[item["name"] for item in self.targets])
        self._loading = True
        self.entry_target.set(target_match["name"])
        self._loading = False
        if not quiet:
            self.status_var.set("设置已自动保存")

    def add_target(self) -> None:
        item = default_target(len(self.targets) + 1)
        self.targets.append(item)
        self._refresh_targets(item["id"])
        self._load_target(item["id"])
        self._mark_stale()

    def duplicate_target(self) -> None:
        source = next(item for item in self.targets if item["id"] == self.current_target_id)
        item = {**source, "id": _identifier("target"), "name": source["name"] + " 副本", "saves": dict(source["saves"])}
        self.targets.append(item)
        self._refresh_targets(item["id"])
        self._load_target(item["id"])
        self._mark_stale()

    def delete_target(self) -> None:
        if len(self.targets) == 1:
            messagebox.showinfo("无法删除", "至少保留一个目标。")
            return
        deleted = self.current_target_id
        self.targets = [item for item in self.targets if item["id"] != deleted]
        fallback = self.targets[0]
        for entry in self.entries:
            if entry.get("target_id") == deleted:
                entry["target_id"] = fallback["id"]
        self._refresh_targets(fallback["id"])
        self._load_target(fallback["id"])
        self._mark_stale()

    def add_entry(self) -> None:
        item = default_entry(len(self.entries) + 1)
        item["target_id"] = self.targets[0]["id"]
        self.entries.append(item)
        self._refresh_entries(item["id"])
        self._load_entry(item["id"])
        self._mark_stale()

    def import_quick_to_advanced(self, request: QuickAttackRequest) -> None:
        """把快速设置复制成新的高级目标和攻击条目，不覆盖已有数据。"""
        target = default_target(len(self.targets) + 1)
        target.update(name="快速计算目标", ac=str(request.target_ac))
        entry = default_entry(len(self.entries) + 1)
        entry.update(
            name="快速攻击",
            target_id=target["id"],
            count=str(request.attack_count),
            attack_bonus=str(request.attack_bonus),
            crit_range=str(request.crit_range),
            power_attack=request.power_attack,
            dice_count=str(request.damage_dice_count),
            dice_sides=str(request.damage_die_sides),
            flat_bonus=str(request.damage_bonus),
            manual_hits=request.manual_hit_count is not None,
            manual_hit_count=str(request.manual_hit_count or 0),
            manual_critical_count=str(request.manual_critical_count),
            advantage="1" if request.roll_mode is RollMode.ADVANTAGE else "0",
            disadvantage="1" if request.roll_mode is RollMode.DISADVANTAGE else "0",
        )
        self.targets.append(target)
        self.entries.append(entry)
        self._refresh_targets(target["id"])
        self._refresh_entries(entry["id"])
        self._load_target(target["id"])
        self._load_entry(entry["id"])
        self.show_advanced()
        self._mark_stale()
        self.status_var.set("已把快速设置新增到高级工作台；原有目标和条目未被覆盖")

    def duplicate_entry(self) -> None:
        source = next(item for item in self.entries if item["id"] == self.current_entry_id)
        item = {**source, "id": _identifier("entry"), "name": source["name"] + " 副本"}
        self.entries.append(item)
        self._refresh_entries(item["id"])
        self._load_entry(item["id"])
        self._mark_stale()

    def delete_entry(self) -> None:
        if len(self.entries) == 1:
            messagebox.showinfo("无法删除", "至少保留一个结算条目。")
            return
        self.entries = [item for item in self.entries if item["id"] != self.current_entry_id]
        self.current_entry_id = self.entries[0]["id"]
        self._refresh_entries(self.current_entry_id)
        self._load_entry(self.current_entry_id)
        self._mark_stale()

    def move_entry(self, delta: int) -> None:
        index = next(i for i, item in enumerate(self.entries) if item["id"] == self.current_entry_id)
        new_index = max(0, min(len(self.entries) - 1, index + delta))
        if new_index != index:
            self.entries[index], self.entries[new_index] = self.entries[new_index], self.entries[index]
            self._refresh_entries(self.current_entry_id)
            self._mark_stale()

    @staticmethod
    def _parse_types(value: str) -> frozenset[str]:
        return frozenset(part.strip() for part in value.replace("，", ",").split(",") if part.strip())

    def _models(self):
        targets = []
        for item in self.targets:
            reduction = int(item.get("fixed_reduction", "0"))
            targets.append(
                Target(
                    item["id"], item["name"], int(item["ac"]),
                    tuple((ability, int(item.get("saves", {}).get(ability, "0"))) for ability in STANDARD_ABILITIES),
                    self._parse_types(item.get("resistances", "")), self._parse_types(item.get("vulnerabilities", "")),
                    self._parse_types(item.get("immunities", "")), self._parse_types(item.get("nonmagical_resistances", "")),
                    bool(item.get("crit_immune", False)),
                    (DamageReduction(reduction),) if reduction > 0 else (),
                )
            )
        return tuple(targets)

    def _component(self, entry: dict[str, Any]) -> DamageComponent:
        policy = RerollPolicy((1, 2), True, True) if entry["great_weapon_fighting"] else RerollPolicy()
        return DamageComponent(
            f"{entry['id']}:base", entry["damage_name"] or "伤害",
            DiceTerm(int(entry["dice_count"]), int(entry["dice_sides"])), int(entry["flat_bonus"]),
            entry["damage_type"], bool(entry["weapon_die"]), bool(entry["magical"]), reroll=policy,
        )

    def _attack_group(self, entry: dict[str, Any]) -> AttackGroup:
        component = self._component(entry)
        components = [component]
        rider_count, rider_sides = int(entry["rider_dice"]), int(entry["rider_sides"])
        rider_name = entry["rider"]
        if rider_name == "偷袭":
            components.append(
                replace(
                    sneak_attack(rider_count, rider_sides),
                    component_id=f"{entry['id']}:sneak",
                    damage_type=entry["damage_type"],
                    magical=bool(entry["magical"]),
                )
            )
        elif rider_name == "至圣斩":
            components.append(replace(divine_smite(rider_count, rider_sides), component_id=f"{entry['id']}:smite"))
        elif rider_name == "凶蛮攻击":
            components.append(
                replace(
                    savage_attacks(rider_sides),
                    component_id=f"{entry['id']}:savage",
                    damage_type=entry["damage_type"],
                    magical=bool(entry["magical"]),
                )
            )
        elif rider_name == "野蛮重击":
            components.append(
                replace(
                    brutal_critical(rider_count, rider_sides),
                    component_id=f"{entry['id']}:brutal",
                    damage_type=entry["damage_type"],
                    magical=bool(entry["magical"]),
                )
            )
        modifiers = []
        if entry["bless"]:
            modifiers.append(DiceModifier("祝福术", DiceTerm(1, 4, 1)))
        if entry["bane"]:
            modifiers.append(DiceModifier("灾祸术", DiceTerm(1, 4, -1)))
        count = int(entry["count"])
        if entry["power_attack"]:
            power_indices = frozenset(range(count))
        else:
            values = [part.strip() for part in entry.get("power_indices", "").replace("，", ",").split(",") if part.strip()]
            power_indices = frozenset(int(value) - 1 for value in values)
            if any(index < 0 or index >= count for index in power_indices):
                raise ValueError("-5/+10 攻击序号必须在本组攻击次数范围内")
        group = AttackGroup(
            entry["id"], entry["name"], entry["target_id"], count, int(entry["attack_bonus"]),
            int(entry["advantage"]), int(entry["disadvantage"]), bool(entry["elven_accuracy"]),
            bool(entry["halfling_lucky"]), int(entry["crit_range"]), tuple(modifiers),
            power_indices, components=tuple(components),
            manual_hit_count=int(entry["manual_hit_count"]) if entry.get("manual_hits") else None,
            manual_critical_count=int(entry["manual_critical_count"]) if entry.get("manual_hits") else 0,
        )
        return apply_attack_preset(group, entry["preset"])

    def run_resolution(self) -> None:
        try:
            self.apply_editors()
            targets = self._models()
            attack_groups = [self._attack_group(entry) for entry in self.entries if entry["mode"] == "attack"]
            sessions = []
            self.attack_session = self.engine.resolve_attacks(attack_groups, targets) if attack_groups else None
            if self.attack_session:
                sessions.append(self.attack_session)
            for entry in self.entries:
                target_ids = tuple(target.target_id for target in targets) if entry["all_targets"] else (entry["target_id"],)
                component = self._component(entry)
                if entry["mode"] == "save":
                    effect = SaveEffect(
                        entry["id"], entry["name"], target_ids, int(entry["dc"]), entry["save_ability"],
                        SAVE_PRESETS[entry["save_outcome"]], (component,),
                    )
                    sessions.append(self.engine.resolve_damage(self.engine.resolve_saves(effect, targets)))
                elif entry["mode"] == "auto":
                    effect = AutoEffect(entry["id"], entry["name"], target_ids, (component,))
                    sessions.append(self.engine.resolve_damage(self.engine.resolve_auto(effect, targets)))
            self.sessions = sessions
            self._stale = False
            self.status_var.set("检定完成；修改输入后需重新投掷")
            self.damage_button.configure(state=tk.NORMAL if self.attack_session else tk.DISABLED)
            self._render()
            if self.attack_session:
                if self.rider_vars:
                    self.result_tabs.select(self.rider_tab)
                    self.result_stage_var.set("检定完成：请在“② 命中后附加”中勾选需要的效果，再点击“③ 结算攻击伤害”。")
                else:
                    self.result_tabs.select(0)
                    self.result_stage_var.set("检定完成：没有需要选择的附加伤害，可直接点击“③ 结算攻击伤害”。")
            else:
                self.result_tabs.select(0)
                self.result_stage_var.set("法术已完成检定与伤害结算，最终结果显示在下方。")
        except (ValueError, RulesError, KeyError) as exc:
            messagebox.showerror("输入错误", str(exc))
            self.status_var.set(f"输入错误：{exc}")
            self.result_stage_var.set(f"无法结算：{exc}")

    def roll_attack_damage(self) -> None:
        if not self.attack_session or self._stale:
            messagebox.showwarning("结果已过期", "请先用当前设置重新投掷检定。")
            return
        selections: dict[str, list[str]] = {}
        for (component_id, attack_id), variable in self.rider_vars.items():
            if variable.get():
                selections.setdefault(component_id, []).append(attack_id)
        try:
            self.attack_session = self.engine.resolve_damage(self.attack_session, selections)
            self.sessions = [self.attack_session if item.mode is ResolutionMode.ATTACK else item for item in self.sessions]
            self.status_var.set("伤害结算完成")
            self._render()
            self.result_tabs.select(0)
            self.result_stage_var.set("攻击伤害结算完成。最终结果显示在“结算结果”中。")
        except RulesError as exc:
            messagebox.showerror("附加伤害选择错误", str(exc))
            self.result_stage_var.set(f"附加伤害选择需要调整：{exc}")

    def reroll_selected(self) -> None:
        refs = [key for key, variable in self.die_vars.items() if variable.get()]
        if not refs:
            return
        self.sessions = [self.engine.reroll_selected(session, refs) for session in self.sessions]
        self.attack_session = next((item for item in self.sessions if item.mode is ResolutionMode.ATTACK), None)
        self.status_var.set("已重骰选中骰子；新结果必须接受")
        self._render()
        self.result_tabs.select(0)
        self.result_stage_var.set("所选骰子已重骰并重新计算最终伤害；新结果必须接受。")

    def _render(self) -> None:
        lines = []
        target_names = {target["id"]: target["name"] for target in self.targets}
        for session in self.sessions:
            if session.mode is ResolutionMode.ATTACK:
                lines.append("【攻击检定】")
                for attack in session.attack_results:
                    raw = format_d20_rolls(attack.d20_rolls) if attack.d20_rolls else "未投 d20"
                    mark = "★重击" if attack.critical else ("✔命中" if attack.hit else "✘未命中")
                    lines.append(f"{attack.group_name} #{attack.index + 1} → {target_names[attack.target_id]}　[{raw}] {attack.explanation}　{mark}")
            elif session.mode is ResolutionMode.SAVE:
                assert session.save_effect
                lines.append(f"【豁免检定：{session.save_effect.name}】")
                for save in session.save_results:
                    lines.append(
                        f"{target_names[save.target_id]}：d20 {save.d20} {save.bonus:+d} = {save.total}　"
                        f"{'成功' if save.succeeded else '失败'}"
                    )
            else:
                assert session.auto_effect
                lines.append(f"【自动伤害：{session.auto_effect.name}】")
            if session.damage_results:
                for result in session.damage_results:
                    details = "；".join(
                        f"{item.damage_type} {item.raw}→{item.final}" + (f"（{item.note}）" if item.note else "")
                        for item in result.by_type
                    )
                    lines.append(f"  {target_names[result.target_id]} 最终伤害 {result.total}：{details}")
            lines.append("")
        self._set_result("\n".join(lines) or "没有可结算的条目。")
        self._render_riders()
        self._render_dice()

    def _render_riders(self) -> None:
        old_values = {key: var.get() for key, var in self.rider_vars.items()}
        for child in self.rider_frame.winfo_children():
            child.destroy()
        self.rider_vars = {}
        if not self.attack_session:
            ttk.Label(self.rider_frame, text="当前没有攻击检定").pack(anchor="w")
            return
        groups = {group.group_id: group for group in self.attack_session.attack_groups}
        any_rider = False
        for attack in self.attack_session.attack_results:
            if not attack.hit:
                continue
            for component in groups[attack.group_id].components:
                if component.scope.value not in ("once_selectable", "selected_hits"):
                    continue
                any_rider = True
                key = (component.component_id, attack.attack_id)
                variable = tk.BooleanVar(value=old_values.get(key, attack.attack_id in self.attack_session.selections().get(component.component_id, ())))
                self.rider_vars[key] = variable
                ttk.Checkbutton(
                    self.rider_frame,
                    text=f"{attack.group_name} #{attack.index + 1}：{component.name}",
                    variable=variable,
                ).pack(anchor="w")
        if not any_rider:
            ttk.Label(self.rider_frame, text="没有需要在命中后选择的附加伤害").pack(anchor="w")

    def _render_dice(self) -> None:
        for child in self.dice_frame.winfo_children():
            child.destroy()
        self.die_vars = {}
        for session in self.sessions:
            for result in session.damage_results:
                for component in result.components:
                    if not component.dice:
                        continue
                    row = ttk.Frame(self.dice_frame)
                    row.pack(fill=tk.X, anchor="w")
                    ttk.Label(row, text=f"{component.name}：").pack(side=tk.LEFT)
                    for index, die in enumerate(component.dice):
                        key = (result.source_id, component.component_id, index)
                        variable = tk.BooleanVar(value=False)
                        self.die_vars[key] = variable
                        text = f"{die.original}→{die.value}" if die.rerolled else str(die.value)
                        ttk.Checkbutton(row, text=text, variable=variable).pack(side=tk.LEFT, padx=2)
        self.reroll_button.configure(state=tk.NORMAL if self.die_vars else tk.DISABLED)
        if not self.die_vars:
            ttk.Label(self.dice_frame, text="投掷伤害后可在此选择单颗骰子").pack(anchor="w")

    def _set_result(self, text: str) -> None:
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", text)
        self.result_text.configure(state=tk.DISABLED)

    def on_close(self) -> None:
        try:
            if self._autosave_after_id is not None:
                self.root.after_cancel(self._autosave_after_id)
                self._autosave_after_id = None
            self.apply_editors(quiet=True)
            self.store.save(
                {
                    "window": {"geometry": self.root.geometry()},
                    "targets": self.targets,
                    "entries": self.entries,
                    "custom_presets": self.custom_presets,
                    "quick": self.quick_page.config_data(),
                    "onboarding_seen": self.onboarding_seen,
                    "help_expanded": self.quick_page.help_visible,
                }
            )
        except Exception as exc:
            if not messagebox.askyesno("配置保存失败", f"无法保存配置：{exc}\n仍要退出吗？"):
                return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = CalculatorApp(root)
    app._attach_traces()
    root.mainloop()
