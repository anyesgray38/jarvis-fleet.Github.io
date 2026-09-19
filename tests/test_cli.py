import json
import unittest
from unittest.mock import Mock

from cli.aegis import AegisCLIError, make_plan


class TestAegisCli(unittest.TestCase):
    def test_planner_accepts_registered_capability(self):
        client = Mock()
        client.chat.return_value = {
            "response": {
                "content": json.dumps({
                    "objective": "inspect the repository",
                    "steps": [{
                        "id": "inspect",
                        "capability": "core.software_engineering",
                        "input": {},
                        "depends_on": [],
                        "verification": {"required": True},
                        "constraints": {}
                    }],
                    "notes": []
                })
            }
        }
        plan = make_plan(client, "inspect the repository")
        self.assertEqual(plan["steps"][0]["capability"], "core.software_engineering")

    def test_planner_rejects_unknown_capability(self):
        client = Mock()
        client.chat.return_value = {
            "response": {
                "content": json.dumps({
                    "objective": "do something",
                    "steps": [{
                        "id": "bad",
                        "capability": "not.registered",
                        "input": {},
                        "depends_on": [],
                        "verification": {"required": True},
                        "constraints": {}
                    }],
                    "notes": []
                })
            }
        }
        with self.assertRaises(AegisCLIError):
            make_plan(client, "do something")


if __name__ == "__main__":
    unittest.main()
