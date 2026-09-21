import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.remote_worker import deterministic_inspection, model_plan, snapshot


class RemoteWorkerTests(unittest.TestCase):
    def test_snapshot_is_read_only_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "README.md").write_text("AEGIS test", encoding="utf-8")
            with patch("jarvis.remote_worker.run") as run_mock:
                run_mock.return_value.stdout = "README.md\n"
                text = snapshot(root)
            self.assertIn("--- README.md ---", text)
            self.assertIn("AEGIS test", text)

    @patch("jarvis.model_service.ModelRuntime")
    def test_inspect_requests_report_without_patch(self, runtime_cls):
        runtime_cls.return_value.chat.return_value = {
            "response": {"content": '{"summary":"ok","report":"three findings"}'}
        }
        result = model_plan("inspect tests", "repo context", "terminal.inspect")
        self.assertEqual(result["report"], "three findings")
        call = runtime_cls.return_value.chat.call_args.kwargs
        self.assertEqual(call["purpose"], "research")
        self.assertTrue(call["local_only"])
        self.assertFalse(call["allow_external"])


    def test_deterministic_inspection_fallback_is_read_only(self):
        report = deterministic_inspection(
            "identify test improvements",
            "--- tests/test_example.py ---\nimport unittest\n"
            "--- .github/workflows/aegis-tests.yml ---\npython3 -m unittest\n",
        )
        self.assertIn("Deterministic read-only inspection fallback", report)
        self.assertIn("1.", report)
        self.assertIn("2.", report)
        self.assertIn("3.", report)

    def test_unsupported_capability_is_not_accepted_by_worker(self):
        from jarvis.remote_worker import CAPABILITIES
        self.assertEqual(CAPABILITIES, {"terminal.inspect", "terminal.execute"})


if __name__ == "__main__":
    unittest.main()
