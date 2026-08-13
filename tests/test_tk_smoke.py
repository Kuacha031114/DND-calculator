"""真实 Tk 组件的轻量冒烟测试。

本地无图形会话时创建 Tk 可能直接终止解释器，因此默认测试集不主动
打开窗口；CI 和有桌面会话的验收环境通过 DND_TK_SMOKE=1 启用。
"""

import json
import os
import tempfile
import tkinter as tk
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from dnd_calculator.config import ConfigLoadResult
from dnd_calculator.engine import RulesEngine
from dnd_calculator.ui import CalculatorApp


class SequenceRng:
    def __init__(self, values):
        self.values = iter(values)

    def randint(self, _minimum, _maximum):
        return next(self.values)


class MemoryConfigStore:
    def __init__(self):
        self.saved = None
        self.backups = []

    def load(self):
        return ConfigLoadResult({"config_version": 1, "onboarding_seen": True})

    def save(self, data):
        self.saved = data

    def backup(self, data, label="before-import"):
        self.backups.append(data)
        return Path(f"config-v3.{label}-test.json")


@unittest.skipUnless(os.environ.get("DND_TK_SMOKE") == "1", "仅在图形会话中运行")
class TkSmokeTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"当前环境无法创建 Tk 窗口：{exc}")
        self.root.withdraw()
        self.store = MemoryConfigStore()
        self.app = CalculatorApp(self.root, self.store)
        self.app._attach_traces()
        self.root.update_idletasks()

    def tearDown(self):
        if hasattr(self, "root"):
            try:
                if self.root.winfo_exists():
                    self.root.destroy()
            except tk.TclError:
                pass

    def test_quick_page_is_default_and_one_click_resolves(self):
        self.assertEqual(self.app.quick_container.winfo_manager(), "pack")
        self.assertEqual(self.app.advanced_container.winfo_manager(), "")
        self.assertEqual(self.app.quick_page.roll_mode.get(), "普通")

        self.app.quick_page.engine = RulesEngine(SequenceRng([15, 6]))
        self.app.quick_page.run()
        self.assertEqual(self.app.quick_page.hit_text.get(), "1/1")
        self.assertEqual(self.app.quick_page.damage_text.get(), "9")
        details = self.app.quick_page.details.get("1.0", tk.END)
        self.assertIn("原始 9", details)
        self.assertIn("固定减伤后 9", details)

    def test_switch_and_quick_import_append_data(self):
        original_counts = (len(self.app.targets), len(self.app.entries))
        request = self.app.quick_page.request()
        self.assertIsNotNone(request)
        self.app.import_quick_to_advanced(request)
        self.root.update_idletasks()

        self.assertEqual(
            (len(self.app.targets), len(self.app.entries)),
            (original_counts[0] + 1, original_counts[1] + 1),
        )
        self.assertEqual(self.app.quick_container.winfo_manager(), "")
        self.assertEqual(self.app.advanced_container.winfo_manager(), "pack")
        self.assertEqual(self.app.entry_mode.get(), "攻击检定")

    def test_quick_manual_hits_do_not_need_ac_roll(self):
        page = self.app.quick_page
        page.manual_hits.set(True)
        page.attack_count.set("3")
        page.manual_hit_count.set("2")
        page.manual_critical_count.set("0")
        page.target_ac.set("")
        page.engine = RulesEngine(SequenceRng([3, 4]))
        page.run()
        self.assertEqual(page.hit_text.get(), "2/3")
        self.assertEqual(page.damage_text.get(), "13")

    def test_advanced_editor_only_shows_fields_for_current_mode(self):
        self.app.show_advanced()
        self.app.entry_mode.set("豁免检定")
        self.root.update_idletasks()
        self.assertEqual(self.app.save_fields.winfo_manager(), "pack")
        self.assertEqual(self.app.attack_fields.winfo_manager(), "")
        self.assertEqual(self.app.all_targets_check.winfo_manager(), "grid")

        self.app.entry_mode.set("自动伤害")
        self.root.update_idletasks()
        self.assertEqual(self.app.auto_fields.winfo_manager(), "pack")
        self.assertEqual(self.app.save_fields.winfo_manager(), "")

        self.app.entry_mode.set("攻击检定")
        self.root.update_idletasks()
        self.assertEqual(self.app.attack_fields.winfo_manager(), "pack")
        self.assertEqual(self.app.all_targets_check.winfo_manager(), "")

    def test_dynamic_damage_rows_keep_one_and_support_reordering(self):
        entry = self.app.entries[0]
        self.assertEqual(len(entry["damage_components"]), 1)
        self.assertIn("disabled", self.app.delete_damage_button.state())

        self.app.add_damage_component("selected_hits")
        added_id = self.app.current_damage_id
        self.assertEqual(len(entry["damage_components"]), 2)
        self.assertNotIn("disabled", self.app.delete_damage_button.state())
        self.app.move_damage_component(-1)
        self.assertEqual(entry["damage_components"][0]["id"], added_id)
        self.app.delete_damage_component()
        self.assertEqual(len(entry["damage_components"]), 1)
        self.assertIn("disabled", self.app.delete_damage_button.state())

    def test_selectable_hit_modifier_precedes_multi_component_damage(self):
        entry = self.app.entries[0]
        entry.update(count="1", attack_bonus="5")
        self.app.target_ac.set("15")
        self.app.add_attack_modifier("once_selectable")
        modifier_id = self.app.current_modifier_id
        self.app.add_damage_component("selected_hits")
        component_id = self.app.current_damage_id
        self.app.damage_name.set("至圣斩")
        self.app.dice_count.set("1")
        self.app.dice_sides.set("6")
        self.app.flat_bonus.set("0")
        self.app.engine = RulesEngine(SequenceRng([8, 4, 5, 6]))

        self.app.run_resolution()
        self.assertFalse(self.app.attack_session.attack_modifiers_resolved)
        attack_id = f"{entry['id']}:0"
        self.app.attack_modifier_vars[modifier_id].set(attack_id)
        self.app.apply_attack_modifiers()
        self.assertTrue(self.app.attack_session.attack_results[0].hit)
        self.app.rider_vars[(component_id, attack_id)].set(True)
        self.app.roll_attack_damage()

        damage = self.app.attack_session.damage_results[0]
        self.assertEqual([item.component_id for item in damage.components], [entry["damage_components"][0]["id"], component_id])
        self.assertEqual(damage.total, 14)
        rendered = self.app.result_text.get("1.0", tk.END)
        self.assertIn("组件 至圣斩", rendered)
        self.assertIn("固定减伤后", rendered)

    def test_analysis_navigation_build_actions_and_error_recovery(self):
        self.app.show_analysis()
        page = self.app.analysis_container
        self.assertEqual(page.winfo_manager(), "pack")
        original = len(page.config["builds"])
        page.add_build()
        self.assertEqual(len(page.config["builds"]), original + 1)
        page.duplicate_build()
        self.assertEqual(len(page.config["builds"]), original + 2)
        page.delete_build()
        self.assertEqual(len(page.config["builds"]), original + 1)
        page.common_vars["target_ac"].set("bad")
        page._commit_and_analyze()
        self.assertIn("所有编辑内容均已保留", page.error_var.get())
        page.common_vars["target_ac"].set("15")
        page._commit_and_analyze()
        self.assertEqual(page.error_var.get(), "")
        self.assertTrue(page.sensitivity_tree.get_children())

    def test_debounced_save_preserves_unknown_platform_fields(self):
        self.app.data["future"] = {"keep": True}
        self.app.data["web"] = {"active_view": "analysis", "onboarding_seen": True}
        self.app.quick_page.target_ac.set("18")
        self.root.after(650, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.store.saved["quick"]["target_ac"], "18")
        self.assertEqual(self.store.saved["future"], {"keep": True})
        self.assertEqual(self.store.saved["web"]["active_view"], "analysis")

    def test_close_cancels_pending_callback_and_forces_final_save(self):
        self.app.quick_page.target_ac.set("19")
        self.assertIsNotNone(self.app._disk_save_after_id)
        self.app.on_close()
        self.assertEqual(self.store.saved["quick"]["target_ac"], "19")
        self.assertIsNone(self.app._disk_save_after_id)

    def test_failed_import_rolls_back_after_creating_backup(self):
        original_name = self.app.targets[0]["name"]
        imported = deepcopy(self.app._compose_config())
        imported["targets"][0]["name"] = "导入目标"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(imported, ensure_ascii=False), encoding="utf-8")
            apply = self.app._apply_imported_config

            def fail_after_apply(data):
                apply(data)
                if data["targets"][0]["name"] == "导入目标":
                    raise RuntimeError("模拟导入界面失败")

            with (
                mock.patch("dnd_calculator.ui.filedialog.askopenfilename", return_value=str(path)),
                mock.patch("dnd_calculator.ui.messagebox.askyesno", return_value=True),
                mock.patch("dnd_calculator.ui.messagebox.showerror") as showerror,
                mock.patch.object(self.app, "_apply_imported_config", side_effect=fail_after_apply),
            ):
                self.app.import_config()
        self.assertEqual(self.app.targets[0]["name"], original_name)
        self.assertEqual(len(self.store.backups), 1)
        self.assertIn("已恢复导入前状态", showerror.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
