"""真实 Tk 组件的轻量冒烟测试。

本地无图形会话时创建 Tk 可能直接终止解释器，因此默认测试集不主动
打开窗口；CI 和有桌面会话的验收环境通过 DND_TK_SMOKE=1 启用。
"""

import os
import tkinter as tk
import unittest

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

    def load(self):
        return ConfigLoadResult({"config_version": 1, "onboarding_seen": True})

    def save(self, data):
        self.saved = data


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
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_quick_page_is_default_and_one_click_resolves(self):
        self.assertEqual(self.app.quick_container.winfo_manager(), "pack")
        self.assertEqual(self.app.advanced_container.winfo_manager(), "")
        self.assertEqual(self.app.quick_page.roll_mode.get(), "普通")

        self.app.quick_page.engine = RulesEngine(SequenceRng([15, 6]))
        self.app.quick_page.run()
        self.assertEqual(self.app.quick_page.hit_text.get(), "1/1")
        self.assertEqual(self.app.quick_page.damage_text.get(), "9")

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


if __name__ == "__main__":
    unittest.main()
