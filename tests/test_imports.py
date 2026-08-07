import unittest


class ImportTests(unittest.TestCase):
    def test_ui_import_does_not_create_a_window(self):
        import dnd_calculator.ui

        self.assertTrue(callable(dnd_calculator.ui.main))


if __name__ == "__main__":
    unittest.main()
