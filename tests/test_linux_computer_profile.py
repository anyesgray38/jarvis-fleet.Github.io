import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LinuxComputerProfileTests(unittest.TestCase):
    def test_profile_declares_existing_active_surface(self):
        profile = json.loads((ROOT / "deploy" / "linux-computer-control.json").read_text())
        self.assertEqual(profile["profile"], "linux-computer-control")
        self.assertIn("computer_operator", profile["active_agents"])
        self.assertNotIn("market", profile["active_agents"])
        self.assertNotIn("business_prospecting", profile["active_agents"])
        for relative in profile["included_paths"]:
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_profile_keeps_risky_controls_off_by_default(self):
        profile = json.loads((ROOT / "deploy" / "linux-computer-control.json").read_text())
        self.assertTrue(all(value is False for value in profile["safety_defaults"].values()))

    def test_export_materializes_only_filtered_linux_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "linux-profile"
            result = subprocess.run(
                [sys.executable, "scripts/export_linux_profile.py", "--output", str(output)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"ok": true', result.stdout)
            exported = json.loads((output / "capabilities/registry.json").read_text())
            self.assertEqual(
                {item["id"] for item in exported["capabilities"]},
                {
                    "core.task_orchestration",
                    "core.desktop_control",
                    "core.browser_automation",
                    "core.chrome_diagnostics",
                    "terminal.read",
                },
            )
            self.assertFalse((output / "trading").exists())
            self.assertFalse((output / "prospecting").exists())


if __name__ == "__main__":
    unittest.main()
