import tempfile
import unittest
from pathlib import Path

from actions.fabric import ActionContext, ActionError, default_fabric


class ActionFabricTests(unittest.TestCase):
    def test_default_actions_are_allow_listed(self):
        fabric = default_fabric()
        self.assertEqual(
            fabric.available(),
            ["filesystem.read", "filesystem.write", "website.create"],
        )

    def test_write_and_read_stay_inside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            context = ActionContext("task-1", Path(directory))
            fabric = default_fabric()
            fabric.execute("filesystem.write", {"path": "site/index.html", "content": "<h1>AEGIS</h1>"}, context)
            result = fabric.execute("filesystem.read", {"path": "site/index.html"}, context)
            self.assertEqual(result.output["content"], "<h1>AEGIS</h1>")

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            context = ActionContext("task-1", Path(directory))
            with self.assertRaises(ActionError):
                default_fabric().execute("filesystem.write", {"path": "../outside", "content": "x"}, context)

    def test_unregistered_action_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            context = ActionContext("task-1", Path(directory))
            with self.assertRaises(ActionError):
                default_fabric().execute("shell.execute", {"command": "uname", "allowed_commands": ["uname"]}, context)


if __name__ == "__main__":
    unittest.main()
