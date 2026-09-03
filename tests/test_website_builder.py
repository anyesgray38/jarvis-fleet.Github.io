import unittest

from website_builder import build_website_action


class WebsiteBuilderTests(unittest.TestCase):
    def test_builds_planner_ready_action(self):
        action = build_website_action(
            task_id="task-123",
            workspace="/tmp/aegis-workspace",
            name="shark-site",
            title="Shark Logistics",
            description="Customer logistics portal",
        )
        self.assertEqual(action["capability"], "core.website_generation")
        self.assertEqual(action["action"], "website.create")
        self.assertEqual(action["input"]["name"], "shark-site")
        self.assertTrue(action["verification"]["required"])
        self.assertIn("self_audit", action["verification"]["checks"])


if __name__ == "__main__":
    unittest.main()
