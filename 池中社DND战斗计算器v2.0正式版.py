# %%
import random
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import ctypes
import json
import os
import sys

# ──────────────────────────────────────────────
# 高DPI适配（Windows专用，让界面在高分辨率屏幕上不模糊）
# ──────────────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ══════════════════════════════════════════════
#  配置文件路径（兼容 PyInstaller 打包为 exe）
# ══════════════════════════════════════════════

def get_config_path():
    """返回配置文件路径。打包为 exe 时保存在 exe 同目录；开发时保存在脚本同目录。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "calculator_config.json")


# ══════════════════════════════════════════════
#  主题配色与字体（统一管理，便于换肤）
# ══════════════════════════════════════════════

class Theme:
    """集中存放界面的配色、字体等样式常量（羊皮纸古风主题）。"""
    # —— 主色调（做旧羊皮纸） ——
    BG        = "#e8dcc0"   # 窗口主背景（深羊皮纸）
    CARD      = "#f5ecd6"   # 卡片背景（浅羊皮纸）
    BORDER    = "#b89968"   # 卡片描边（旧皮革棕）
    TEXT      = "#3a2c1a"   # 主文字（深墨褐）
    TEXT_SUB  = "#7d6a4d"   # 次要文字（淡墨褐）
    INPUT     = "#fbf6e8"   # 输入框底色（米白）
    DISABLED  = "#c2b393"   # 禁用控件底色

    # —— 命中区主题（古铜金） ——
    ATK       = "#8a6d3b"   # 命中主色（古铜）
    ATK_DARK  = "#6b5329"   # 命中按钮按下色
    ATK_SOFT  = "#ede0c4"   # 命中浅色背景

    # —— 伤害区主题（蜡封赤红） ——
    DMG       = "#9c3b2e"   # 伤害主色（蜡封红）
    DMG_DARK  = "#782c22"   # 伤害按钮按下色
    DMG_SOFT  = "#ecd9c6"   # 伤害浅色背景

    # —— 底栏 ——
    FOOTER    = "#c9b98a"   # 底栏背景（中调羊皮纸）

    # —— 字体（运行时按屏幕尺寸填充） ——
    FAMILY    = "KaiTi"               # 楷体，契合古卷风格
    MONO      = "Consolas"            # 结果区等宽字体
    TITLE     = None
    HEAD      = None
    LABEL     = None
    BTN       = None
    RESULT    = None
    FOOTER_F  = None                  # 底栏字体

    @classmethod
    def init_fonts(cls, base):
        """根据基准字号生成各级字体。"""
        cls.TITLE   = (cls.FAMILY, base + 6, "bold")
        cls.HEAD    = (cls.FAMILY, base + 1, "bold")
        cls.LABEL   = (cls.FAMILY, base)
        cls.BTN     = (cls.FAMILY, base + 1, "bold")
        cls.RESULT  = (cls.MONO,   base)
        cls.FOOTER_F = (cls.FAMILY, max(8, base - 1))


# ══════════════════════════════════════════════
#  骰子投掷核心函数
# ══════════════════════════════════════════════

def roll_d20(mode="normal"):
    """投掷d20，支持普通/优势/劣势三种模式。
    返回 (最终结果, 展示文字)，例如 (15, '(15)') 或 (18, '(18/12)')。
    """
    r1, r2 = random.randint(1, 20), random.randint(1, 20)
    if mode == "advantage":
        return max(r1, r2), f"({r1}/{r2})"
    elif mode == "disadvantage":
        return min(r1, r2), f"({r1}/{r2})"
    else:  # normal
        return r1, f"({r1})"


def roll_dice_group(dice_type, count):
    """投掷一组同类型骰子，例如 dice_type='d6', count=3。
    返回 (总点数, 各骰结果列表)，例如 (11, [4, 3, 4])。
    """
    if not dice_type or count <= 0:
        return 0, []
    sides = int(dice_type[1:])  # 从 'd8' 中解析出面数 8
    rolls = [random.randint(1, sides) for _ in range(count)]
    return sum(rolls), rolls


def collect_dice_config(name_vars, type_vars, count_vars, enable_vars=None):
    """从界面变量中读取骰子配置，过滤掉未填写或未勾选的项。
    返回有效骰子列表，每项为 (名称, 类型, 数量)。
    """
    dice = []
    for i, (name_v, type_v, count_v) in enumerate(zip(name_vars, type_vars, count_vars)):
        if enable_vars and not enable_vars[i].get():
            continue
        dtype = type_v.get()
        count = int(count_v.get())
        if dtype and count > 0:
            dice.append((name_v.get().strip(), dtype, count))
    return dice


def roll_dice_list(dice_config, crit=False):
    """对一组骰子配置执行投掷，大成功时骰子数量翻倍。
    返回 (总点数, 结果描述字符串)，例如 (9, '武器:2d6(4/5)')。
    """
    total = 0
    parts = []
    for name, dtype, count in dice_config:
        actual_count = count * 2 if crit else count  # 大成功：骰子翻倍（5e核心规则）
        subtotal, rolls = roll_dice_group(dtype, actual_count)
        total += subtotal
        prefix = f"{name}:" if name else ""
        parts.append(f"{prefix}{actual_count}{dtype}({'/'.join(map(str, rolls))})")
    desc = "+".join(parts)
    return total, desc


def set_spinbox_value(spin, value):
    """以编程方式设置 Spinbox 的当前值（覆盖原内容）。"""
    spin.delete(0, tk.END)
    spin.insert(0, str(value))


def set_result_text(widget, text, color=None):
    """更新 ScrolledText 结果框的内容，颜色通过 tag 控制。"""
    color = color or Theme.TEXT
    widget.config(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.tag_config("t", foreground=color)
    widget.insert("1.0", text, "t")
    widget.config(state=tk.DISABLED)


# ══════════════════════════════════════════════
#  配置保存 / 读取
# ══════════════════════════════════════════════

def save_config():
    """将当前界面所有参数序列化为 JSON 并写入配置文件。"""
    def spin_get(key):
        return ui[key].get()

    cfg = {
        # 命中区基础数值
        "atk_prof":    spin_get("atk_prof"),
        "atk_ability": spin_get("atk_ability"),
        "atk_extra":   spin_get("atk_extra"),
        "atk_times":   spin_get("atk_times"),
        "atk_ac":      spin_get("atk_ac"),
        # 攻击方式
        "atk_type":       ui["atk_type"].get(),
        # 重击范围
        "atk_crit_range": spin_get("atk_crit_range"),
        # 共享的 -5/+10 专长
        "feat":           ui["feat"].get(),
        # 命中骰子
        "atk_dice_names":   [v.get() for v in ui["atk_dice_names"]],
        "atk_dice_types":   [v.get() for v in ui["atk_dice_types"]],
        "atk_dice_counts":  [v.get() for v in ui["atk_dice_counts"]],
        "atk_dice_enables": [v.get() for v in ui["atk_dice_enables"]],
        # 伤害区
        "act_bonus":   spin_get("act_bonus"),
        "act_times":   spin_get("act_times"),
        "bon_bonus":   spin_get("bon_bonus"),
        "bon_times":   spin_get("bon_times"),
        # 重骰阈值
        "reroll_thr":  spin_get("reroll_thr"),
        # 动作伤害骰子
        "act_dice_names":   [v.get() for v in ui["act_dice_names"]],
        "act_dice_types":   [v.get() for v in ui["act_dice_types"]],
        "act_dice_counts":  [v.get() for v in ui["act_dice_counts"]],
        "act_dice_enables": [v.get() for v in ui["act_dice_enables"]],
        # 附赠动作伤害骰子
        "bon_dice_names":   [v.get() for v in ui["bon_dice_names"]],
        "bon_dice_types":   [v.get() for v in ui["bon_dice_types"]],
        "bon_dice_counts":  [v.get() for v in ui["bon_dice_counts"]],
        "bon_dice_enables": [v.get() for v in ui["bon_dice_enables"]],
    }
    try:
        with open(get_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # 保存失败静默忽略，不影响正常使用


def load_config():
    """从配置文件读取上次保存的参数并填入界面控件。"""
    try:
        with open(get_config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return  # 首次运行或文件损坏时直接使用默认值

    def spin_set(key, fallback="0"):
        if key in cfg:
            set_spinbox_value(ui[key], cfg[key])

    def var_list_set(ui_key, cfg_key):
        vals = cfg.get(cfg_key, [])
        for i, v in enumerate(ui[ui_key]):
            if i < len(vals):
                v.set(vals[i])

    spin_set("atk_prof")
    spin_set("atk_ability")
    spin_set("atk_extra")
    spin_set("atk_times")
    spin_set("atk_ac")
    spin_set("atk_crit_range")
    if "atk_type" in cfg:
        ui["atk_type"].set(cfg["atk_type"])
    if "feat" in cfg:
        ui["feat"].set(cfg["feat"])

    var_list_set("atk_dice_names",   "atk_dice_names")
    var_list_set("atk_dice_types",   "atk_dice_types")
    var_list_set("atk_dice_counts",  "atk_dice_counts")
    var_list_set("atk_dice_enables", "atk_dice_enables")

    spin_set("act_bonus")
    spin_set("act_times")
    spin_set("bon_bonus")
    spin_set("bon_times")
    spin_set("reroll_thr")

    var_list_set("act_dice_names",   "act_dice_names")
    var_list_set("act_dice_types",   "act_dice_types")
    var_list_set("act_dice_counts",  "act_dice_counts")
    var_list_set("act_dice_enables", "act_dice_enables")

    var_list_set("bon_dice_names",   "bon_dice_names")
    var_list_set("bon_dice_types",   "bon_dice_types")
    var_list_set("bon_dice_counts",  "bon_dice_counts")
    var_list_set("bon_dice_enables", "bon_dice_enables")


def on_close():
    """窗口关闭前保存配置，再销毁窗口。"""
    save_config()
    root.destroy()


# ══════════════════════════════════════════════
#  命中投掷逻辑
# ══════════════════════════════════════════════

def run_attack_roll():
    """读取命中投掷区域的所有参数，进行多次d20投掷并展示结果。
    若设置了目标AC（>0），则自动统计命中次数并回填动作伤害的命中次数。
    """
    try:
        proficiency = int(ui["atk_prof"].get())
        ability_mod = int(ui["atk_ability"].get())
        extra_bonus = int(ui["atk_extra"].get())
        times       = int(ui["atk_times"].get())
        target_ac   = int(ui["atk_ac"].get())
        crit_range  = int(ui["atk_crit_range"].get())  # 重击触发最低值（默认20）
        use_feat    = ui["feat"].get()
        mode        = ui["atk_type"].get()
        extra_dice  = collect_dice_config(
            ui["atk_dice_names"], ui["atk_dice_types"], ui["atk_dice_counts"],
            ui["atk_dice_enables"]
        )
    except ValueError:
        set_result_text(ui["atk_result"], "⚠ 请输入有效的整数", Theme.DMG)
        return

    results   = []
    all_crits = []
    hit_crits = []
    hit_count = 0

    for _ in range(times):
        raw, d20_text = roll_d20(mode)

        hit_adjust = -5 if use_feat else 0

        dice_total, dice_desc = roll_dice_list(extra_dice)
        dice_text = f"+{dice_desc}" if dice_desc else ""

        total = raw + hit_adjust + proficiency + ability_mod + extra_bonus + dice_total

        extra_text = f"+{extra_bonus}" if extra_bonus != 0 else ""
        feat_text  = " [-5+10]" if use_feat else ""
        line = f"{d20_text}+{proficiency}+{ability_mod}{extra_text}{dice_text} = {total}{feat_text}"

        is_crit = (raw >= crit_range)  # 重击范围：自然值 >= 设定阈值
        is_miss = (raw == 1)
        if is_crit:
            line += "  ★大成功！"
        if is_miss:
            line += "  ☠大失败！"

        if target_ac > 0:
            if is_crit:
                hit = True
            elif is_miss:
                hit = False
            else:
                hit = total >= target_ac
            if hit:
                hit_count += 1
                hit_crits.append(is_crit)
                line += "  ✔命中"
            else:
                line += "  ✘未命中"

        results.append(line)
        all_crits.append(is_crit)

    if target_ac > 0:
        results.append("")
        results.append(f"对 AC {target_ac} —— 命中 {hit_count}/{times} 次")
        set_spinbox_value(ui["act_times"], hit_count)
        state["last_crits"] = hit_crits
    else:
        state["last_crits"] = all_crits

    set_result_text(ui["atk_result"], "\n".join(results))

    state["use_feat"] = use_feat
    state["attacked"] = True
    ui["dmg_btn"].config(state=tk.NORMAL, bg=Theme.DMG, cursor="hand2")


# ══════════════════════════════════════════════
#  伤害投掷逻辑
# ══════════════════════════════════════════════

def signed(n):
    """返回带符号的整数字符串，例如 3→'+3'，-2→'-2'。"""
    return f"+{n}" if n >= 0 else f"{n}"


def build_damage_section(title, bonus, times, dice_config, feat_bonus, crits):
    """构建一个伤害区段的结构化数据（含每颗骰子的可重骰信息）。
    返回 dict：{title, bonus, feat_bonus, hits:[{is_crit, groups:[{name, sides, dice:[die...]}]}]}。
    每颗骰子 die = {sides, value, selected, btn}。
    """
    hits = []
    for i in range(times):
        is_crit = crits[i] if i < len(crits) else False
        groups = []
        for name, dtype, count in dice_config:
            sides = int(dtype[1:])
            actual = count * 2 if is_crit else count   # 大成功：骰子翻倍
            dice = [{"sides": sides, "value": random.randint(1, sides),
                     "selected": False, "btn": None}
                    for _ in range(actual)]
            groups.append({"name": name, "sides": sides, "dice": dice})
        hits.append({"is_crit": is_crit, "groups": groups})
    return {"title": title, "bonus": bonus, "feat_bonus": feat_bonus, "hits": hits}


def iter_dice(data):
    """遍历伤害数据中的所有骰子。"""
    for sec in data["sections"]:
        for hit in sec["hits"]:
            for grp in hit["groups"]:
                for die in grp["dice"]:
                    yield die


def hit_value(sec, hit):
    """计算单次命中的伤害值（骰子点数之和 + 伤害加值 + 专长加值）。"""
    s = sum(die["value"] for grp in hit["groups"] for die in grp["dice"])
    return s + sec["bonus"] + sec["feat_bonus"]


def run_damage_roll():
    """读取伤害投掷区域的所有参数，投掷并构建可交互的伤害结果。"""
    if not state.get("attacked"):
        set_result_text(ui["dmg_result"], "请先进行命中投掷", Theme.TEXT_SUB)
        return

    try:
        act_bonus  = int(ui["act_bonus"].get())
        act_times  = int(ui["act_times"].get())
        bon_bonus  = int(ui["bon_bonus"].get())
        bon_times  = int(ui["bon_times"].get())
        use_feat   = ui["feat"].get()              # 共享专长开关
    except ValueError:
        state["dmg_data"] = None
        set_result_text(ui["dmg_result"], "⚠ 请输入有效的整数", Theme.DMG)
        return

    feat_bonus = 10 if use_feat else 0
    crits      = state.get("last_crits", [])

    act_dice = collect_dice_config(
        ui["act_dice_names"], ui["act_dice_types"], ui["act_dice_counts"],
        ui["act_dice_enables"]
    )
    bon_dice = collect_dice_config(
        ui["bon_dice_names"], ui["bon_dice_types"], ui["bon_dice_counts"],
        ui["bon_dice_enables"]
    )

    sections = []
    if act_times > 0:
        sections.append(build_damage_section("【动作伤害】", act_bonus, act_times,
                                              act_dice, feat_bonus, crits))
    if bon_times > 0:
        sections.append(build_damage_section("【附赠动作伤害】", bon_bonus, bon_times,
                                              bon_dice, feat_bonus, crits))

    state["dmg_data"] = {"sections": sections}
    render_damage_result()


# ──────────────────────────────────────────────
#  伤害结果渲染与重骰
# ──────────────────────────────────────────────

def style_die_button(die):
    """根据选中状态设置骰子按钮的配色。"""
    btn = die["btn"]
    if btn is None:
        return
    if die["selected"]:
        btn.config(bg=Theme.DMG, fg="white", activebackground=Theme.DMG_DARK)
    else:
        btn.config(bg=Theme.INPUT, fg=Theme.TEXT, activebackground=Theme.DMG_SOFT)


def toggle_die(die):
    """点击骰子按钮：切换其选中状态。"""
    die["selected"] = not die["selected"]
    style_die_button(die)


def make_die_button(parent, die):
    """为一颗骰子创建可选中的按钮。"""
    btn = tk.Button(parent, text=str(die["value"]), font=Theme.RESULT,
                    width=3, padx=1, pady=0, bd=1, relief=tk.RIDGE,
                    cursor="hand2", takefocus=0,
                    command=lambda: toggle_die(die))
    die["btn"] = btn
    style_die_button(die)
    return btn


def render_damage_result():
    """根据 state['dmg_data'] 重新渲染伤害结果区（骰子为可点击按钮）。"""
    txt = ui["dmg_result"]
    txt.config(state=tk.NORMAL)
    txt.delete("1.0", tk.END)

    # 统一配置文本标签样式
    txt.tag_config("head",  foreground=Theme.DMG,      font=Theme.HEAD)
    txt.tag_config("label", foreground=Theme.TEXT,     font=Theme.RESULT)
    txt.tag_config("sub",   foreground=Theme.TEXT_SUB, font=Theme.RESULT)
    txt.tag_config("eq",    foreground=Theme.DMG_DARK, font=Theme.RESULT)
    txt.tag_config("total", foreground=Theme.DMG,      font=Theme.BTN)

    data = state.get("dmg_data")
    if not data or not data["sections"]:
        txt.insert(tk.END, "（本次没有需要投掷的伤害）", "sub")
        txt.config(state=tk.NORMAL)   # 保持启用以确保后续嵌入按钮可点击
        return

    grand_total = 0
    for sec in data["sections"]:
        txt.insert(tk.END, sec["title"] + "\n", "head")
        for hi, hit in enumerate(sec["hits"]):
            crit_mark = " ★" if hit["is_crit"] else ""
            txt.insert(tk.END, f"  第{hi+1}次{crit_mark}  ", "label")

            any_token = False
            for grp in hit["groups"]:
                if not grp["dice"]:
                    continue
                if any_token:
                    txt.insert(tk.END, " + ", "label")
                if grp["name"]:
                    txt.insert(tk.END, f"{grp['name']}:", "label")
                for di, die in enumerate(grp["dice"]):
                    if di > 0:
                        txt.insert(tk.END, " ")
                    txt.window_create(tk.END, window=make_die_button(txt, die))
                any_token = True

            if sec["bonus"] != 0:
                txt.insert(tk.END, f" {signed(sec['bonus'])}", "label")
            if sec["feat_bonus"] != 0:
                txt.insert(tk.END, f" {signed(sec['feat_bonus'])}", "label")

            txt.insert(tk.END, f"  = {hit_value(sec, hit)}\n", "eq")

        sec_total = sum(hit_value(sec, h) for h in sec["hits"])
        grand_total += sec_total
        avg = sec_total / len(sec["hits"]) if sec["hits"] else 0
        txt.insert(tk.END, f"  ── 合计 {sec_total}　平均 {avg:.1f}\n\n", "sub")

    txt.insert(tk.END, f"⚔ 总伤害：{grand_total}", "total")
    # 保持 NORMAL，使嵌入的骰子按钮可点击；只读由 <Key> 拦截实现
    txt.config(state=tk.NORMAL)


def reroll_selected():
    """重骰所有被选中的骰子，然后清除选中并刷新结果。"""
    data = state.get("dmg_data")
    if not data:
        return
    for die in iter_dice(data):
        if die["selected"]:
            die["value"] = random.randint(1, die["sides"])
            die["selected"] = False
    render_damage_result()


def reroll_below():
    """重骰所有点数 ≤ 阈值的骰子（如战斗风格「重武器精通」重投 1 和 2：阈值设 2）。"""
    data = state.get("dmg_data")
    if not data:
        return
    try:
        thr = int(ui["reroll_thr"].get())
    except ValueError:
        return
    for die in iter_dice(data):
        if die["value"] <= thr:          # 闭区间：点数 ≤ 阈值时触发
            die["value"] = random.randint(1, die["sides"])
            die["selected"] = False
    render_damage_result()


def clear_selection():
    """清除所有骰子的选中状态。"""
    data = state.get("dmg_data")
    if not data:
        return
    for die in iter_dice(data):
        die["selected"] = False
    render_damage_result()


# ══════════════════════════════════════════════
#  界面辅助组件
# ══════════════════════════════════════════════

def make_card(parent, bg=None):
    """创建一个带描边的卡片容器，返回内部内容框（已留好内边距）。"""
    bg = bg or Theme.CARD
    outer = tk.Frame(parent, bg=Theme.BORDER)
    outer.pack(fill=tk.X, padx=14, pady=7)
    inner = tk.Frame(outer, bg=bg)
    inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
    pad = tk.Frame(inner, bg=bg)
    pad.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
    return pad


def make_card_expand(parent, bg=None):
    """与 make_card 相同，但外层框也随父容器垂直伸展（用于结果卡片）。"""
    bg = bg or Theme.CARD
    outer = tk.Frame(parent, bg=Theme.BORDER)
    outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=7)
    inner = tk.Frame(outer, bg=bg)
    inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
    pad = tk.Frame(inner, bg=bg)
    pad.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
    return pad


def section_header(parent, text, accent, bg):
    """创建带左侧竖条强调的小节标题。"""
    row = tk.Frame(parent, bg=bg)
    row.pack(fill=tk.X, pady=(0, 8))
    tk.Frame(row, bg=accent, width=4, height=18).pack(side=tk.LEFT, padx=(0, 8))
    tk.Label(row, text=text, font=Theme.HEAD, bg=bg, fg=Theme.TEXT).pack(side=tk.LEFT)


def hover_button(parent, text, command, color, color_dark):
    """创建扁平风格按钮，带鼠标悬停变色效果。"""
    btn = tk.Button(parent, text=text, command=command, font=Theme.BTN,
                    bg=color, fg="white", activebackground=color_dark,
                    activeforeground="white", relief=tk.FLAT, bd=0,
                    padx=24, pady=9, cursor="hand2")
    btn.bind("<Enter>", lambda e: btn.config(bg=color_dark) if str(btn["state"]) != "disabled" else None)
    btn.bind("<Leave>", lambda e: btn.config(bg=color) if str(btn["state"]) != "disabled" else None)
    return btn


def small_button(parent, text, command, color, color_dark):
    """创建紧凑型扁平按钮（用于重骰控制条），带鼠标悬停变色。"""
    btn = tk.Button(parent, text=text, command=command, font=Theme.LABEL,
                    bg=color, fg="white", activebackground=color_dark,
                    activeforeground="white", relief=tk.FLAT, bd=0,
                    padx=10, pady=3, cursor="hand2")
    btn.bind("<Enter>", lambda e: btn.config(bg=color_dark))
    btn.bind("<Leave>", lambda e: btn.config(bg=color))
    return btn


def styled_spinbox(parent, default="0", from_=-99, to=999, width=None, textvariable=None):
    """创建带上下增减按钮的数值输入框（Spinbox），统一羊皮纸样式。"""
    spin = tk.Spinbox(parent, from_=from_, to=to, font=Theme.LABEL,
                      textvariable=textvariable, justify=tk.LEFT,
                      relief=tk.FLAT, fg=Theme.TEXT, bg=Theme.INPUT,
                      buttonbackground=Theme.ATK_SOFT, readonlybackground=Theme.INPUT,
                      highlightthickness=1, highlightbackground=Theme.BORDER,
                      highlightcolor=Theme.ATK, **({"width": width} if width else {}))
    if textvariable is None:
        spin.delete(0, tk.END)
        spin.insert(0, default)
    return spin


def labeled_entry(parent, label_text, default="0", bg=None, from_=-99, to=999):
    """创建一对「标签 + 数值调节框」，返回 Spinbox 控件（带上下按钮）。"""
    bg = bg or Theme.CARD
    tk.Label(parent, text=label_text, font=Theme.LABEL, bg=bg, fg=Theme.TEXT_SUB).pack(anchor=tk.W)
    spin = styled_spinbox(parent, default=default, from_=from_, to=to)
    spin.pack(pady=(2, 8), fill=tk.X, ipady=3)
    return spin


def build_dice_grid(parent, accent, rows=3, cols=2, bg=None, dice_values=None):
    """构建 rows×cols 个骰子行，返回 (名称变量列表, 类型变量列表, 数量变量列表, 启用变量列表)。
    每行左侧有勾选框，未勾选时该行骰子不参与计算。
    """
    bg = bg or Theme.CARD
    if dice_values is None:
        dice_values = ["", "d4", "d6", "d8", "d10", "d12", "d20"]

    name_vars, type_vars, count_vars, enable_vars = [], [], [], []

    col_frames = []
    for _ in range(cols):
        f = tk.Frame(parent, bg=bg)
        f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        col_frames.append(f)

    for col in range(cols):
        for row in range(rows):
            idx = col * rows + row
            row_frame = tk.Frame(col_frames[col], bg=bg)
            row_frame.pack(fill=tk.X, pady=3)

            name_v   = tk.StringVar()
            type_v   = tk.StringVar(value="")
            count_v  = tk.StringVar(value="0")
            enable_v = tk.BooleanVar(value=True)

            name_vars.append(name_v)
            type_vars.append(type_v)
            count_vars.append(count_v)
            enable_vars.append(enable_v)

            tk.Checkbutton(row_frame, variable=enable_v, bg=bg,
                           activebackground=bg, selectcolor=Theme.INPUT,
                           relief=tk.FLAT, bd=0).pack(side=tk.LEFT, padx=(0, 2))
            tk.Label(row_frame, text=f"{idx+1}", font=Theme.LABEL, bg=accent,
                     fg="white", width=2).pack(side=tk.LEFT, padx=(0, 4))
            tk.Entry(row_frame, textvariable=name_v, width=7, font=Theme.LABEL,
                     relief=tk.FLAT, fg=Theme.TEXT, bg=Theme.INPUT, highlightthickness=1,
                     highlightbackground=Theme.BORDER).pack(side=tk.LEFT, padx=2, ipady=2)
            ttk.Combobox(row_frame, textvariable=type_v, values=dice_values,
                         width=5, state="readonly").pack(side=tk.LEFT, padx=2)
            tk.Label(row_frame, text="×", font=Theme.LABEL, bg=bg, fg=Theme.TEXT_SUB).pack(side=tk.LEFT)
            styled_spinbox(row_frame, from_=0, to=99, width=4,
                           textvariable=count_v).pack(side=tk.LEFT, padx=2, ipady=2)

    return name_vars, type_vars, count_vars, enable_vars


def make_scrolled_result(parent, bg=None, height=8):
    """创建只读的 ScrolledText 结果框，统一羊皮纸样式。"""
    bg = bg or Theme.CARD
    st = ScrolledText(parent, font=Theme.RESULT, bg=bg, fg=Theme.TEXT_SUB,
                      relief=tk.FLAT, bd=0, wrap=tk.WORD, height=height,
                      state=tk.DISABLED, insertontime=0, cursor="arrow",
                      highlightthickness=1, highlightbackground=Theme.BORDER,
                      selectbackground=Theme.ATK_SOFT)
    # 滚动条颜色尽量贴合主题（ScrolledText 内部为 tk.Text，无法完全自定义）
    return st


def build_footer(parent):
    """构建底部贡献者署名栏。"""
    tk.Frame(parent, bg=Theme.BORDER, height=1).pack(fill=tk.X)

    bar = tk.Frame(parent, bg=Theme.FOOTER)
    bar.pack(fill=tk.X)

    tk.Label(bar, text="池中社 DND 战斗计算器  v2.0",
             font=Theme.FOOTER_F, bg=Theme.FOOTER, fg=Theme.ATK).pack(side=tk.LEFT, padx=14, pady=5)

    tk.Label(bar, text="制作者：池中社。感谢池中社全体成员的测试与反馈！欢迎关注我们的小红书账号：池中社TRPG，获取更多相关工具和内容！",
             font=Theme.FOOTER_F, bg=Theme.FOOTER, fg=Theme.TEXT_SUB).pack(side=tk.RIGHT, padx=14, pady=5)


# ══════════════════════════════════════════════
#  左侧：命中投掷面板
# ══════════════════════════════════════════════

def build_attack_panel(parent):
    """构建命中投掷面板，所有控件引用存入全局 ui 字典。"""
    accent = Theme.ATK

    # —— 顶部标题条 ——
    header = tk.Frame(parent, bg=accent)
    header.pack(fill=tk.X)
    tk.Label(header, text="⚔  命 中 投 掷", font=Theme.TITLE,
             bg=accent, fg="white", pady=12).pack()

    body = tk.Frame(parent, bg=Theme.BG)
    body.pack(fill=tk.BOTH, expand=True)

    # —— 基础数值卡片 ——
    card = make_card(body)
    section_header(card, "基础加值", accent, Theme.CARD)
    grid = tk.Frame(card, bg=Theme.CARD)
    grid.pack(fill=tk.X)
    left  = tk.Frame(grid, bg=Theme.CARD)
    right = tk.Frame(grid, bg=Theme.CARD)
    left.pack(side=tk.LEFT,  fill=tk.BOTH, expand=True, padx=(0, 8))
    right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
    ui["atk_prof"]    = labeled_entry(left,  "熟练加值",   "0")
    ui["atk_ability"] = labeled_entry(left,  "属性调整值", "0")
    ui["atk_extra"]   = labeled_entry(right, "额外加值",   "0")
    ui["atk_times"]   = labeled_entry(right, "攻击次数",   "1", from_=0)

    # —— 目标AC卡片 ——
    card = make_card(body)
    section_header(card, "目标护甲等级 AC", accent, Theme.CARD)
    ac_row = tk.Frame(card, bg=Theme.CARD)
    ac_row.pack(fill=tk.X)
    tk.Label(ac_row, text="AC（设为 0 则不自动判定命中）：",
             font=Theme.LABEL, bg=Theme.CARD, fg=Theme.TEXT_SUB).pack(side=tk.LEFT)
    ui["atk_ac"] = styled_spinbox(ac_row, default="0", from_=0, to=99, width=6)
    ui["atk_ac"].pack(side=tk.LEFT, padx=6, ipady=2)

    # —— 攻击方式卡片 ——
    card = make_card(body)
    section_header(card, "攻击方式", accent, Theme.CARD)
    type_row = tk.Frame(card, bg=Theme.CARD)
    type_row.pack(fill=tk.X)
    ui["atk_type"] = tk.StringVar(value="normal")
    for text, val in [("普通", "normal"), ("优势", "advantage"), ("劣势", "disadvantage")]:
        tk.Radiobutton(type_row, text=text, variable=ui["atk_type"], value=val,
                       bg=Theme.CARD, fg=Theme.TEXT, font=Theme.LABEL,
                       activebackground=Theme.CARD, selectcolor=Theme.ATK_SOFT).pack(side=tk.LEFT, padx=10)

    # 重击范围（默认20；咒剑/勇士等可调低至19或18）
    crit_row = tk.Frame(card, bg=Theme.CARD)
    crit_row.pack(fill=tk.X, pady=(8, 0))
    tk.Label(crit_row, text="重击触发范围（自然骰 ≥ 此值）：",
             font=Theme.LABEL, bg=Theme.CARD, fg=Theme.TEXT_SUB).pack(side=tk.LEFT)
    ui["atk_crit_range"] = styled_spinbox(crit_row, default="20", from_=1, to=20, width=4)
    ui["atk_crit_range"].pack(side=tk.LEFT, padx=6, ipady=2)
    tk.Label(crit_row, text="（普通=20，勇士=19，咒剑=18）",
             font=Theme.LABEL, bg=Theme.CARD, fg=Theme.TEXT_SUB).pack(side=tk.LEFT)

    # —— -5/+10 专长（共享，命中与伤害均使用此开关） ——
    tk.Checkbutton(card, text="启用 -5/+10 专长（命中 -5，伤害 +10）",
                   variable=ui["feat"], bg=Theme.CARD, fg=Theme.TEXT,
                   font=Theme.LABEL, activebackground=Theme.CARD,
                   selectcolor=Theme.ATK_SOFT).pack(anchor=tk.W, pady=(8, 0))

    # —— 额外命中骰子卡片 ——
    card = make_card(body)
    section_header(card, "额外命中加值骰子", accent, Theme.CARD)
    dice_box = tk.Frame(card, bg=Theme.CARD)
    dice_box.pack(fill=tk.X)
    ui["atk_dice_names"], ui["atk_dice_types"], ui["atk_dice_counts"], ui["atk_dice_enables"] = \
        build_dice_grid(dice_box, accent)

    # —— 投掷按钮 ——
    hover_button(body, "🎲  进行命中投掷", run_attack_roll, accent, Theme.ATK_DARK).pack(pady=10)

    # —— 结果卡片（可滚动） ——
    card = make_card_expand(body)
    section_header(card, "命中结果", accent, Theme.CARD)
    ui["atk_result"] = make_scrolled_result(card, bg=Theme.CARD, height=8)
    ui["atk_result"].pack(fill=tk.BOTH, expand=True)
    set_result_text(ui["atk_result"], "等待投掷…", Theme.TEXT_SUB)


# ══════════════════════════════════════════════
#  右侧：伤害投掷面板
# ══════════════════════════════════════════════

def build_damage_tab(parent, prefix):
    """构建单个伤害 Tab（动作 act / 附赠动作 bon）的内容。"""
    accent = Theme.DMG
    default_times = "1" if prefix == "act" else "0"

    pad = tk.Frame(parent, bg=Theme.CARD)
    pad.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    if prefix == "act":
        tk.Label(pad, text="（设置AC后，命中次数将由命中投掷自动填入；也可手动调整）",
                 font=Theme.LABEL, bg=Theme.CARD, fg=Theme.TEXT_SUB).pack(anchor=tk.W, pady=(0, 6))

    grid = tk.Frame(pad, bg=Theme.CARD)
    grid.pack(fill=tk.X)
    left  = tk.Frame(grid, bg=Theme.CARD)
    right = tk.Frame(grid, bg=Theme.CARD)
    left.pack(side=tk.LEFT,  fill=tk.BOTH, expand=True, padx=(0, 8))
    right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
    ui[f"{prefix}_bonus"] = labeled_entry(left,  "伤害加值", "0")
    ui[f"{prefix}_times"] = labeled_entry(right, "命中次数", default_times, from_=0)

    section_header(pad, "一次命中的伤害骰子", accent, Theme.CARD)
    dice_box = tk.Frame(pad, bg=Theme.CARD)
    dice_box.pack(fill=tk.X)
    ui[f"{prefix}_dice_names"], ui[f"{prefix}_dice_types"], ui[f"{prefix}_dice_counts"], ui[f"{prefix}_dice_enables"] = \
        build_dice_grid(dice_box, accent,
                        dice_values=["", "d4", "d6", "d8", "d10", "d12", "d20", "d100"])


def build_damage_panel(parent):
    """构建伤害投掷面板。"""
    accent = Theme.DMG

    # —— 顶部标题条 ——
    header = tk.Frame(parent, bg=accent)
    header.pack(fill=tk.X)
    tk.Label(header, text="🔥  伤 害 投 掷", font=Theme.TITLE,
             bg=accent, fg="white", pady=12).pack()

    body = tk.Frame(parent, bg=Theme.BG)
    body.pack(fill=tk.BOTH, expand=True)

    # —— 动作 / 附赠动作 标签页 ——
    card = make_card(body)
    nb = ttk.Notebook(card)
    nb.pack(fill=tk.BOTH, expand=True)
    act_tab = tk.Frame(nb, bg=Theme.CARD)
    bon_tab = tk.Frame(nb, bg=Theme.CARD)
    nb.add(act_tab, text="  动作伤害  ")
    nb.add(bon_tab, text="  附赠动作伤害  ")
    build_damage_tab(act_tab, prefix="act")
    build_damage_tab(bon_tab, prefix="bon")

    # —— 投掷按钮（初始禁用，需先命中投掷） ——
    ui["dmg_btn"] = hover_button(body, "🎲  进行伤害投掷", run_damage_roll, accent, Theme.DMG_DARK)
    ui["dmg_btn"].config(state=tk.DISABLED, bg=Theme.DISABLED, cursor="arrow")
    ui["dmg_btn"].pack(pady=10)

    # —— 结果卡片（可滚动，骰子为可点击按钮） ——
    card = make_card_expand(body)
    section_header(card, "伤害结果（点击骰子数字可选中）", accent, Theme.CARD)

    # 重骰控制条
    ctrl = tk.Frame(card, bg=Theme.CARD)
    ctrl.pack(fill=tk.X, pady=(0, 6))
    small_button(ctrl, "🎲 重骰选中", reroll_selected, accent, Theme.DMG_DARK).pack(side=tk.LEFT)
    small_button(ctrl, "清除选择", clear_selection, Theme.TEXT_SUB, Theme.ATK_DARK).pack(side=tk.LEFT, padx=(6, 0))
    # 一键重骰低于阈值的骰子
    tk.Label(ctrl, text="　快速重骰：点数 ≤", font=Theme.LABEL,
             bg=Theme.CARD, fg=Theme.TEXT_SUB).pack(side=tk.LEFT)
    ui["reroll_thr"] = styled_spinbox(ctrl, default="2", from_=1, to=99, width=4)
    ui["reroll_thr"].pack(side=tk.LEFT, padx=4, ipady=1)
    small_button(ctrl, "🎲 重骰", reroll_below, accent, Theme.DMG_DARK).pack(side=tk.LEFT, padx=(2, 0))

    ui["dmg_result"] = make_scrolled_result(card, bg=Theme.CARD, height=8)
    ui["dmg_result"].pack(fill=tk.BOTH, expand=True)
    # 保持只读（禁止键盘输入），但嵌入的骰子按钮仍可点击
    ui["dmg_result"].bind("<Key>", lambda e: "break")
    set_result_text(ui["dmg_result"], "请先进行命中投掷", Theme.TEXT_SUB)


# ══════════════════════════════════════════════
#  主程序入口
# ══════════════════════════════════════════════

# 全局状态：跨函数共享的运行时数据
state = {
    "attacked":   False,
    "last_crits": [],
    "use_feat":   False,
    "dmg_data":   None,    # 最近一次伤害投掷的结构化数据（供重骰使用）
}

# 全局 UI 控件引用字典
ui = {}

# 共享的 -5/+10 专长变量必须在 Tk 实例创建之后才能实例化，
# 因此先创建窗口，再建变量，再构建面板。

# ── 主窗口 ──
root = tk.Tk()
root.title("池中社DND战斗计算器v2.0")
root.configure(bg=Theme.BG)

sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
root.geometry(f"{min(1040, int(sw * 0.8))}x{min(860, int(sh * 0.87))}")
root.minsize(820, 620)
base_size = max(9, int(min(sw, sh) / 110))
Theme.init_fonts(base_size)

# 共享专长变量（Tk 实例已就绪）
ui["feat"] = tk.BooleanVar(value=False)

# —— ttk 控件统一样式 ——
style = ttk.Style()
try:
    style.theme_use("clam")
except Exception:
    pass
style.configure("TNotebook", background=Theme.CARD, borderwidth=0)
style.configure("TNotebook.Tab", font=Theme.LABEL, padding=(14, 6),
                background=Theme.ATK_SOFT, foreground=Theme.TEXT_SUB)
style.map("TNotebook.Tab",
          background=[("selected", Theme.DMG)],
          foreground=[("selected", "white")])
style.configure("TCombobox", fieldbackground=Theme.INPUT, background=Theme.INPUT,
                foreground=Theme.TEXT, arrowcolor=Theme.TEXT)

# ── 左右分栏 ──
paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashwidth=6,
                       sashrelief=tk.FLAT, bg=Theme.BG)
paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

atk_frame = tk.Frame(paned, bg=Theme.BG)
dmg_frame = tk.Frame(paned, bg=Theme.BG)
paned.add(atk_frame, stretch="always")
paned.add(dmg_frame, stretch="always")

# ── 构建两侧面板 ──
build_attack_panel(atk_frame)
build_damage_panel(dmg_frame)

# ── 底部署名栏 ──
build_footer(root)

# ── 读取上次保存的配置 ──
load_config()

# ── 关闭时自动保存 ──
root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()
