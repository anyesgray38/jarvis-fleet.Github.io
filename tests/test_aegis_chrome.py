import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aegis_chrome import ChromeControlError, play_bedtime_music
from security.safety import SafetySettings


class AegisChromeTests(unittest.TestCase):
    def test_requires_desktop_safety_control_before_connecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = SafetySettings(Path(tmp) / "safety.json")
            with self.assertRaises(PermissionError):
                play_bedtime_music(safety=settings)

    def test_reports_missing_devtools_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = SafetySettings(Path(tmp) / "safety.json")
            settings.set("desktop_control", True)
            with self.assertRaises(ChromeControlError):
                play_bedtime_music(cdp_url="http://127.0.0.1:1", safety=settings)

    def test_cli_bounds_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = SafetySettings(Path(tmp) / "safety.json")
            settings.set("desktop_control", True)
            with patch("aegis_chrome.ChromeSession"):
                with self.assertRaises(ValueError):
                    play_bedtime_music(min_seconds=3600, max_seconds=3600, safety=settings)


if __name__ == "__main__":
    unittest.main()
