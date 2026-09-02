import copy
import json
import re
import unittest
from pathlib import Path

from fleet.config import FleetConfigError, validate_fleet_config


class FleetConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path("fleet/config.example.json")
        cls.data = json.loads(cls.path.read_text())

    def test_example_config_is_valid(self):
        self.assertIs(validate_fleet_config(self.data), self.data)
        self.assertEqual(self.data["network"]["provider"], "tailscale")

    def test_example_config_contains_references_not_credentials(self):
        enrollment = self.data["enrollment"]
        signing = self.data["signing"]
        self.assertRegex(enrollment["bootstrap_token_env"], r"^[A-Za-z_][A-Za-z0-9_]*$")
        self.assertRegex(signing["secret_env"], r"^[A-Za-z_][A-Za-z0-9_]*$")
        self.assertNotIn("value", enrollment)
        self.assertNotIn("value", signing)

    def test_missing_enrollment_is_rejected(self):
        data = copy.deepcopy(self.data)
        del data["enrollment"]
        with self.assertRaises(FleetConfigError):
            validate_fleet_config(data)

    def test_duplicate_node_ids_are_rejected(self):
        data = copy.deepcopy(self.data)
        data["nodes"].append(copy.deepcopy(data["nodes"][0]))
        with self.assertRaises(FleetConfigError):
            validate_fleet_config(data)

    def test_public_bind_cannot_be_enabled(self):
        data = copy.deepcopy(self.data)
        data["network"]["allow_public_bind"] = True
        with self.assertRaises(FleetConfigError):
            validate_fleet_config(data)

    def test_request_age_is_bounded(self):
        data = copy.deepcopy(self.data)
        data["signing"]["max_request_age_seconds"] = 301
        with self.assertRaises(FleetConfigError):
            validate_fleet_config(data)


if __name__ == "__main__":
    unittest.main()
