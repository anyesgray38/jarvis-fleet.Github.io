import json
import unittest
from pathlib import Path

class FleetConfigTests(unittest.TestCase):
    def test_example_config_is_valid_and_has_no_secrets(self):
        data = json.loads(Path("fleet/config.example.json").read_text())
        text = Path("fleet/config.example.json").read_text().lower()
        self.assertEqual(data["network"]["provider"], "tailscale")
        for secret_marker in ("api_key", "password", "token", "secret"):
            self.assertNotIn(secret_marker, text)

if __name__ == "__main__":
    unittest.main()
