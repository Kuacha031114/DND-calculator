from pathlib import Path
import json
import tempfile
import unittest

from dnd_calculator.config import CONFIG_VERSION, ConfigStore, user_config_dir


class ConfigTests(unittest.TestCase):
    def test_platform_paths_are_separate_from_executable(self):
        self.assertEqual(
            user_config_dir("win32", {"APPDATA": "C:/Data"}),
            Path("C:/Data") / "池中社" / "DND战斗计算器",
        )
        self.assertEqual(
            user_config_dir("darwin", {}).parts[-3:],
            ("Library", "Application Support", "池中社 DND战斗计算器"),
        )

    def test_atomic_round_trip_adds_version(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            store.save({"window": {"width": 900}})
            result = store.load()
            self.assertEqual(result.data["config_version"], CONFIG_VERSION)
            self.assertEqual(result.data["window"]["width"], 900)
            self.assertFalse(store.path.with_suffix(".tmp").exists())

    def test_corrupt_config_is_backed_up(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            store.directory.mkdir(exist_ok=True)
            store.path.write_text("{broken", encoding="utf-8")
            result = store.load()
            self.assertTrue(result.warning)
            self.assertFalse(store.path.exists())
            self.assertEqual(len(list(store.directory.glob("config-v3.corrupt-*.json"))), 1)

    def test_old_version_is_not_loaded_or_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            store.directory.mkdir(exist_ok=True)
            store.path.write_text(json.dumps({"config_version": 99, "legacy": True}), encoding="utf-8")
            result = store.load()
            self.assertNotIn("legacy", result.data)
            self.assertTrue(store.path.exists())

    def test_v31_optional_ui_fields_preserve_advanced_data(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            payload = {
                "targets": [{"id": "old-target"}],
                "entries": [{"id": "old-entry"}],
                "custom_presets": {"常用攻击": {}},
                "quick": {"target_ac": "17"},
                "onboarding_seen": True,
                "help_expanded": False,
            }
            store.save(payload)
            loaded = store.load().data
            self.assertEqual(loaded["targets"], payload["targets"])
            self.assertEqual(loaded["entries"], payload["entries"])
            self.assertEqual(loaded["custom_presets"], payload["custom_presets"])
            self.assertEqual(loaded["quick"]["target_ac"], "17")


if __name__ == "__main__":
    unittest.main()
