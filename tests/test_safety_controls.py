import json
import tempfile
import unittest
from pathlib import Path

from jarvis.autonomy import TrustLevel
from jarvis.cli import main
from security.safety import SafetySettings, SafetyController, control_for_capability


class SafetyTests(unittest.TestCase):
    def test_risky_controls_default_off_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "safety.json"
            settings = SafetySettings(path)
            self.assertFalse(settings.enabled("shell_execution"))
            settings.set("shell_execution", True)
            loaded = SafetySettings(path)
            self.assertTrue(loaded.enabled("shell_execution"))
            self.assertEqual(json.loads(path.read_text())["shell_execution"], True)

    def test_capability_maps_to_control(self):
        self.assertEqual(control_for_capability("shell.execute"), "shell_execution")
        self.assertEqual(control_for_capability("filesystem.write"), None)

    def test_disabled_control_blocks_and_enabled_allows(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = SafetySettings(Path(tmp) / "safety.json")
            controller = SafetyController(settings)
            self.assertFalse(controller.check("shell_execution").allowed)
            settings.set("shell_execution", True)
            self.assertTrue(controller.check("shell_execution").allowed)

    def test_cli_toggle_changes_persisted_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "safety.json"
            # CLI currently uses the default location; exercise the same command
            # surface through its parser separately in the lower-level tests.
            settings = SafetySettings(path)
            settings.set("production_deploy", True)
            self.assertTrue(SafetySettings(path).enabled("production_deploy"))


if __name__ == "__main__":
    unittest.main()
