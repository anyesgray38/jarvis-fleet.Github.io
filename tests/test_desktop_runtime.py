import json
import tempfile
import unittest
from pathlib import Path

from desktop_runtime import DesktopController
from security.safety import SafetySettings


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.calls = []
        self.cursor = {"x": 100, "y": 100}

    def status(self):
        return {"name": self.name, "available": True}

    def observe(self):
        return {"ok": True, "backend": self.name, "screen": {"width": 1000, "height": 800},
                "cursor": dict(self.cursor), "windows": [{"title": "AEGIS Test Window"}]}

    def screenshot(self):
        import base64
        return {"ok": True, "backend": self.name, "mime_type": "image/png",
                "image_base64": base64.b64encode(b"fake-png").decode("ascii")}

    def action(self, action, arguments):
        self.calls.append((action, arguments))
        if action == "move":
            self.cursor = {"x": arguments["x"], "y": arguments["y"]}
        return {"ok": True, "action": action}

    def close(self):
        return None


class DesktopRuntimeTests(unittest.TestCase):
    def controller(self, tmp, enabled=False):
        safety = SafetySettings(Path(tmp) / "safety.json")
        safety.set("desktop_control", enabled)
        return DesktopController(FakeBackend(), safety, Path(tmp) / "audit.jsonl")

    def test_observe_and_health_are_available_without_input_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = self.controller(tmp)
            self.assertTrue(controller.health()["ok"])
            self.assertEqual(controller.observe()["windows"][0]["title"], "AEGIS Test Window")

    def test_input_is_fail_closed_until_explicitly_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = self.controller(tmp)
            with self.assertRaises(PermissionError):
                controller.action("click", {"x": 10, "y": 10})
            self.assertEqual(controller.backend.calls, [])

    def test_sensitive_typing_is_blocked_even_when_control_is_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = self.controller(tmp, enabled=True)
            with self.assertRaises(PermissionError):
                controller.action("type", {"text": "secret", "sensitive": True})

    def test_action_redacts_text_and_stop_is_latched(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = self.controller(tmp, enabled=True)
            result = controller.action("type", {"text": "hello"})
            self.assertTrue(result["ok"])
            controller.stop("test")
            with self.assertRaises(PermissionError):
                controller.action("click", {"x": 10, "y": 10})
            record = json.loads((Path(tmp) / "audit.jsonl").read_text().splitlines()[-2])
            self.assertEqual(record["arguments"]["text_length"], 5)
            self.assertNotIn("hello", (Path(tmp) / "audit.jsonl").read_text())

    def test_bounded_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = self.controller(tmp, enabled=True)
            self.assertTrue(controller.verify({"backend_available": True})["satisfied"])
            self.assertTrue(controller.verify({"active_window_contains": "test window"})["satisfied"])
            controller.action("move", {"x": 12, "y": 14})
            self.assertTrue(controller.verify({"pointer_at": {"x": 12, "y": 14}})["satisfied"])


if __name__ == "__main__":
    unittest.main()
