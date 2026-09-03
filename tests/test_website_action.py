import tempfile
import unittest
from pathlib import Path

from actions.fabric import ActionContext, ActionError, default_fabric


class WebsiteActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.context = ActionContext(task_id="website-test", workspace=self.workspace)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_fabric_registers_website_create(self):
        self.assertIn("website.create", default_fabric().available())

    def test_creates_static_project(self):
        result = default_fabric().execute(
            "website.create",
            {"name": "demo-site", "title": "Demo Site", "description": "A test site."},
            self.context,
        )
        project = self.workspace / "demo-site"
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.output["files"], ["README.md", "index.html", "script.js", "styles.css"])
        for filename in result.output["files"]:
            self.assertTrue((project / filename).is_file())
        self.assertIn("Demo Site", (project / "index.html").read_text())

    def test_rejects_nested_or_traversal_project_names(self):
        for name in ("../escape", "nested/site", "..", "."):
            with self.subTest(name=name):
                with self.assertRaises(ActionError):
                    default_fabric().execute(
                        "website.create",
                        {"name": name, "title": "X", "description": "Y"},
                        self.context,
                    )

    def test_requires_explicit_overwrite_for_nonempty_project(self):
        fabric = default_fabric()
        fabric.execute(
            "website.create",
            {"name": "demo", "title": "First", "description": "Original"},
            self.context,
        )
        with self.assertRaises(ActionError):
            fabric.execute(
                "website.create",
                {"name": "demo", "title": "Second", "description": "Updated"},
                self.context,
            )
        result = fabric.execute(
            "website.create",
            {"name": "demo", "title": "Second", "description": "Updated", "overwrite": True},
            self.context,
        )
        self.assertTrue(result.output["overwrote"])
        self.assertIn("Second", (self.workspace / "demo" / "index.html").read_text())

    def test_rejects_invalid_accent(self):
        with self.assertRaises(ActionError):
            default_fabric().execute(
                "website.create",
                {"name": "demo", "title": "X", "description": "Y", "accent": "red"},
                self.context,
            )


if __name__ == "__main__":
    unittest.main()
