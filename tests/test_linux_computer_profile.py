import json
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


if __name__ == "__main__":
    unittest.main()
