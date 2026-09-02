import json
import re
import unittest
from pathlib import Path


class FleetConfigTests(unittest.TestCase):
    def test_example_config_is_valid_and_has_no_secrets(self):
        path = Path("fleet/config.example.json")
        data = json.loads(path.read_text())
        text = path.read_text().lower()

        self.assertEqual(data["network"]["provider"], "tailscale")

        # Environment-variable references are configuration metadata, not
        # credentials. Reject literal credential assignments while allowing
        # names such as `bootstrap_token_env` and `secret_env`.
        self.assertNotRegex(
            text,
            r'"(?:api_key|password|token|secret)"\s*:\s*"(?![a-z0-9_]+_env\b)[^"]+',
        )
        self.assertNotRegex(
            text,
            r'"(?:api_key|password|token|secret)"\s*:\s*\[',
        )

        self.assertRegex(text, r'"bootstrap_token_env"\s*:\s*"[a-z0-9_]+"')
        self.assertRegex(text, r'"secret_env"\s*:\s*"[a-z0-9_]+"')


if __name__ == "__main__":
    unittest.main()
