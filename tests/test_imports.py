import unittest


class ImportTests(unittest.TestCase):
    def test_ui_import_does_not_create_a_window(self):
        import dnd_calculator.ui

        self.assertTrue(callable(dnd_calculator.ui.main))

    def test_advanced_workspace_interface_imports_without_a_window(self):
        from dnd_calculator.advanced_ui import AdvancedWorkspace

        self.assertTrue(callable(AdvancedWorkspace.append_quick))
        self.assertTrue(callable(AdvancedWorkspace.export_state))


if __name__ == "__main__":
    unittest.main()
