"""桌面版强度与时长工作区。"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from copy import deepcopy
from tkinter import ttk
from typing import Any

from .analysis import analyze_encounter_bundle, default_build, normalize_analysis

ROLL_LABELS = {
    "普通": "normal", "优势": "advantage", "劣势": "disadvantage",
    "三骰取高（精灵精准）": "elven_accuracy",
}
ROLL_VALUES = {value: key for key, value in ROLL_LABELS.items()}


class AnalysisPage(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        data: Mapping[str, Any],
        background: str,
        family: str,
        on_change: Callable[[dict[str, Any]], None],
    ) -> None:
        super().__init__(parent, bg=background)
        self.family = family
        self.on_change = on_change
        self.config = normalize_analysis(data)
        self.current_build_id = str(self.config["builds"][0]["id"])
        self._loading = False
        self._after_id: str | None = None
        self._build_ui()
        self._attach_traces()
        self.load_config(self.config)

    def _build_ui(self) -> None:
        canvas = tk.Canvas(self, bg=self.cget("bg"), highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.body = ttk.Frame(canvas, padding=14)
        window = canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))

        heading = ttk.Frame(self.body)
        heading.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(heading, text="强度与时长", font=(self.family, 18, "bold")).pack(side=tk.LEFT)
        ttk.Label(heading, text="构筑期望值比较与 DM 战斗时长基线", foreground="#7d6a4d").pack(side=tk.LEFT, padx=12)

        self.common_vars = {
            "target_ac": tk.StringVar(), "monster_count": tk.StringVar(), "hp_each": tk.StringVar(),
            "party_uptime_percent": tk.StringVar(), "damage_multiplier": tk.StringVar(),
            "desired_rounds": tk.StringVar(),
        }
        common = ttk.LabelFrame(self.body, text="共同目标与遭遇参数", padding=9)
        common.pack(fill=tk.X, pady=(0, 9))
        common_fields = (
            ("目标 AC", "target_ac", 6), ("怪物数量", "monster_count", 6),
            ("每只怪物 HP", "hp_each", 8), ("输出在线率 %", "party_uptime_percent", 8),
            ("伤害倍率", "damage_multiplier", 8), ("目标轮数", "desired_rounds", 8),
        )
        for column, (label, key, width) in enumerate(common_fields):
            frame = ttk.Frame(common)
            frame.grid(row=0, column=column, padx=4, sticky="w")
            ttk.Label(frame, text=label).pack(anchor="w")
            ttk.Entry(frame, textvariable=self.common_vars[key], width=width).pack(anchor="w")

        builds = ttk.LabelFrame(self.body, text="构筑方案", padding=9)
        builds.pack(fill=tk.X, pady=(0, 9))
        self.build_tree = ttk.Treeview(builds, columns=("name", "enabled", "dpr"), show="headings", height=4)
        for key, label, width in (("name", "名称", 230), ("enabled", "计入队伍", 80), ("dpr", "DPR", 90)):
            self.build_tree.heading(key, text=label)
            self.build_tree.column(key, width=width, anchor="center" if key != "name" else "w")
        self.build_tree.pack(fill=tk.X)
        self.build_tree.bind("<<TreeviewSelect>>", self._select_build)
        actions = ttk.Frame(builds)
        actions.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(actions, text="新增构筑", command=self.add_build).pack(side=tk.LEFT)
        ttk.Button(actions, text="复制", command=self.duplicate_build).pack(side=tk.LEFT, padx=3)
        self.delete_button = ttk.Button(actions, text="删除", command=self.delete_build)
        self.delete_button.pack(side=tk.LEFT)

        self.build_vars = {
            "name": tk.StringVar(), "enabled": tk.BooleanVar(), "attack_bonus": tk.StringVar(),
            "attacks_per_round": tk.StringVar(), "roll_mode": tk.StringVar(), "crit_range": tk.StringVar(),
            "damage_dice_count": tk.StringVar(), "damage_die_sides": tk.StringVar(), "damage_bonus": tk.StringVar(),
            "power_attack": tk.BooleanVar(), "crit_extra_dice": tk.StringVar(), "rider_dice_count": tk.StringVar(),
            "rider_die_sides": tk.StringVar(), "rider_bonus": tk.StringVar(),
            "rider_doubles_on_crit": tk.BooleanVar(), "guaranteed_damage": tk.StringVar(),
        }
        editor = ttk.LabelFrame(self.body, text="编辑当前构筑（自动保存）", padding=9)
        editor.pack(fill=tk.X, pady=(0, 9))
        fields = (
            ("名称", "name", 16), ("命中加值", "attack_bonus", 7), ("每轮攻击", "attacks_per_round", 7),
            ("重击下限", "crit_range", 7), ("伤害骰数", "damage_dice_count", 7),
            ("伤害骰面", "damage_die_sides", 7), ("固定加值", "damage_bonus", 7),
            ("重击额外骰", "crit_extra_dice", 7), ("首次附伤骰", "rider_dice_count", 7),
            ("附伤骰面", "rider_die_sides", 7), ("附伤固定值", "rider_bonus", 7),
            ("每轮固定伤害", "guaranteed_damage", 9),
        )
        for index, (label, key, width) in enumerate(fields):
            frame = ttk.Frame(editor)
            frame.grid(row=(index // 6) * 2, column=index % 6, padx=4, pady=3, sticky="w")
            ttk.Label(frame, text=label).pack(anchor="w")
            ttk.Entry(frame, textvariable=self.build_vars[key], width=width).pack(anchor="w")
        options = ttk.Frame(editor)
        options.grid(row=4, column=0, columnspan=6, sticky="w", pady=(6, 0))
        ttk.Label(options, text="投骰方式").pack(side=tk.LEFT)
        ttk.Combobox(options, textvariable=self.build_vars["roll_mode"], values=tuple(ROLL_LABELS), state="readonly", width=21).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(options, text="计入 DM 队伍", variable=self.build_vars["enabled"]).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(options, text="减 5 加 10", variable=self.build_vars["power_attack"]).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(options, text="附伤重击翻倍", variable=self.build_vars["rider_doubles_on_crit"]).pack(side=tk.LEFT, padx=10)

        self.error_var = tk.StringVar()
        ttk.Label(self.body, textvariable=self.error_var, foreground="#9c3b2e", wraplength=1000).pack(fill=tk.X)
        results = ttk.LabelFrame(self.body, text="分析结果", padding=9)
        results.pack(fill=tk.X, pady=(4, 9))
        self.summary_vars = {key: tk.StringVar(value="—") for key in ("raw", "adjusted", "rounds", "suggestion")}
        for column, (label, key) in enumerate((
            ("队伍原始 DPR", "raw"), ("有效 DPR", "adjusted"), ("预计轮数", "rounds"), ("目标轮数建议", "suggestion"),
        )):
            frame = ttk.Frame(results)
            frame.grid(row=0, column=column, padx=12, sticky="w")
            ttk.Label(frame, text=label, foreground="#7d6a4d").pack(anchor="w")
            ttk.Label(frame, textvariable=self.summary_vars[key], font=(self.family, 15, "bold")).pack(anchor="w")

        self.result_tree = ttk.Treeview(self.body, columns=("name", "hit", "crit", "once", "per", "dpr"), show="headings", height=5)
        for key, label, width in (
            ("name", "构筑", 190), ("hit", "命中率", 85), ("crit", "重击率", 85),
            ("once", "至少命中一次", 105), ("per", "单次期望", 90), ("dpr", "DPR", 90),
        ):
            self.result_tree.heading(key, text=label)
            self.result_tree.column(key, width=width, anchor="center" if key != "name" else "w")
        self.result_tree.pack(fill=tk.X, pady=(0, 9))

        sensitivity_box = ttk.LabelFrame(self.body, text="AC 敏感性", padding=7)
        sensitivity_box.pack(fill=tk.X)
        self.sensitivity_tree = ttk.Treeview(sensitivity_box, columns=("ac", "raw", "adjusted", "rounds"), show="headings", height=7)
        for key, label, width in (("ac", "AC", 60), ("raw", "原始 DPR", 100), ("adjusted", "有效 DPR", 100), ("rounds", "预计轮数", 100)):
            self.sensitivity_tree.heading(key, text=label)
            self.sensitivity_tree.column(key, width=width, anchor="center")
        self.sensitivity_tree.pack(fill=tk.X)

    def _attach_traces(self) -> None:
        for variable in (*self.common_vars.values(), *self.build_vars.values()):
            variable.trace_add("write", self._schedule_update)

    def _schedule_update(self, *_args: object) -> None:
        if self._loading:
            return
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(150, self._commit_and_analyze)

    def _save_current(self) -> None:
        build = next((item for item in self.config["builds"] if item["id"] == self.current_build_id), None)
        if build:
            for key, variable in self.build_vars.items():
                value = variable.get()
                build[key] = ROLL_LABELS.get(value, value) if key == "roll_mode" else value
        for key, variable in self.common_vars.items():
            self.config[key] = variable.get()

    def _commit_and_analyze(self) -> None:
        self._after_id = None
        self._save_current()
        self.on_change(deepcopy(self.config))
        self.refresh_results()

    def refresh_results(self) -> None:
        target_text = str(self.config.get("target_ac", ""))
        sensitivity = []
        if target_text.lstrip("-").isdigit():
            target = int(target_text)
            sensitivity = list(dict.fromkeys(max(1, min(99, target - 4 + index)) for index in range(9)))
        try:
            bundle = analyze_encounter_bundle(self.config, sensitivity)
        except ValueError as exc:
            self.error_var.set(f"暂时无法更新结果：{exc}。所有编辑内容均已保留。")
            self._render_results(None)
            return
        self.error_var.set("")
        self._render_results(bundle)

    def _render_results(self, bundle: dict[str, Any] | None) -> None:
        self.result_tree.delete(*self.result_tree.get_children())
        self.sensitivity_tree.delete(*self.sensitivity_tree.get_children())
        if bundle is None:
            for variable in self.summary_vars.values():
                variable.set("—")
            return
        result = bundle["result"]
        rounds = result["estimated_rounds"]
        self.summary_vars["raw"].set(f"{result['raw_party_dpr']:.1f}")
        self.summary_vars["adjusted"].set(f"{result['adjusted_party_dpr']:.1f}")
        self.summary_vars["rounds"].set("—" if rounds is None else f"{rounds:.2f}")
        self.summary_vars["suggestion"].set(f"每只 {result['suggested_hp_each']:.0f} HP / {result['suggested_monster_count']:.1f} 只")
        dpr_by_id = {}
        for build in result["builds"]:
            dpr_by_id[build["id"]] = build["dpr"]
            self.result_tree.insert("", tk.END, values=(
                build["name"], f"{build['hit_probability'] * 100:.1f}%", f"{build['critical_probability'] * 100:.1f}%",
                f"{build['at_least_one_hit_probability'] * 100:.1f}%", f"{build['damage_per_attack']:.1f}", f"{build['dpr']:.1f}",
            ))
        for row in bundle["sensitivity"]:
            item = row["result"]
            self.sensitivity_tree.insert("", tk.END, values=(
                row["ac"], f"{item['raw_party_dpr']:.1f}", f"{item['adjusted_party_dpr']:.1f}",
                "—" if item["estimated_rounds"] is None else f"{item['estimated_rounds']:.2f}",
            ))
        for item in self.config["builds"]:
            if self.build_tree.exists(item["id"]):
                self.build_tree.item(item["id"], values=(item["name"], "是" if item["enabled"] else "否", f"{dpr_by_id.get(item['id'], 0):.1f}"))

    def load_config(self, data: Mapping[str, Any]) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.config = normalize_analysis(data)
        self.current_build_id = str(self.config["builds"][0]["id"])
        self._loading = True
        for key, variable in self.common_vars.items():
            variable.set(self.config.get(key, ""))
        self._refresh_builds()
        self._load_build(self.current_build_id)
        self._loading = False
        self.refresh_results()

    def config_data(self) -> dict[str, Any]:
        self._save_current()
        return deepcopy(self.config)

    def _refresh_builds(self) -> None:
        self.build_tree.delete(*self.build_tree.get_children())
        for item in self.config["builds"]:
            self.build_tree.insert("", tk.END, iid=item["id"], values=(item["name"], "是" if item["enabled"] else "否", "—"))
        self.build_tree.selection_set(self.current_build_id)
        self.delete_button.configure(state=tk.DISABLED if len(self.config["builds"]) == 1 else tk.NORMAL)

    def _load_build(self, build_id: str) -> None:
        build = next(item for item in self.config["builds"] if item["id"] == build_id)
        self.current_build_id = build_id
        self._loading = True
        for key, variable in self.build_vars.items():
            value = ROLL_VALUES.get(str(build.get(key)), build.get(key, "")) if key == "roll_mode" else build.get(key, "")
            variable.set(value)
        self._loading = False

    def _select_build(self, _event: object = None) -> None:
        selected = self.build_tree.selection()
        if not selected or selected[0] == self.current_build_id or self._loading:
            return
        self._save_current()
        self._load_build(selected[0])

    def add_build(self) -> None:
        self._save_current()
        item = default_build(len(self.config["builds"]) + 1)
        self.config["builds"].append(item)
        self.current_build_id = item["id"]
        self._refresh_builds()
        self._load_build(item["id"])
        self._schedule_update()

    def duplicate_build(self) -> None:
        self._save_current()
        source = next(item for item in self.config["builds"] if item["id"] == self.current_build_id)
        item = {**deepcopy(source), "id": default_build()["id"], "name": f"{source['name']}副本", "enabled": False}
        self.config["builds"].append(item)
        self.current_build_id = item["id"]
        self._refresh_builds()
        self._load_build(item["id"])
        self._schedule_update()

    def delete_build(self) -> None:
        if len(self.config["builds"]) == 1:
            return
        self.config["builds"] = [item for item in self.config["builds"] if item["id"] != self.current_build_id]
        self.current_build_id = self.config["builds"][0]["id"]
        self._refresh_builds()
        self._load_build(self.current_build_id)
        self._schedule_update()
