import json
import unittest
import io
from contextlib import redirect_stdout

from jarvis.chrome_diagnostics import ChromeDiagnosticsAgent
from jarvis.cli import main


class ChromeDiagnosticsTests(unittest.TestCase):
    def test_missing_browser_returns_actionable_read_only_diagnosis(self):
        def unavailable(_url, _timeout):
            return {"reachable": False, "error": "connection refused"}

        agent = ChromeDiagnosticsAgent(
            endpoint_probe=unavailable,
            executable_finder=lambda _binary: None,
            process_counter=lambda: 0,
        )
        result = agent.diagnose()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("No Chrome/Chromium", result["diagnosis"])
        self.assertTrue(result["read_only"])
        self.assertTrue(result["recommendations"])


    def test_installed_browser_gets_start_command_when_not_running(self):
        agent = ChromeDiagnosticsAgent(
            endpoint_probe=lambda _url, _timeout: {"reachable": False},
            executable_finder=lambda _binary: "/usr/bin/google-chrome",
            process_counter=lambda: 0,
        )
        result = agent.diagnose()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("--remote-debugging-port=9222", result["recommendations"][0])


    def test_ready_requires_attachable_page(self):
        agent = ChromeDiagnosticsAgent(
            endpoint_probe=lambda _url, _timeout: {"reachable": True, "pages": 1, "attachable_pages": 1, "browser": "Chrome/1"},
            executable_finder=lambda _binary: "/usr/bin/google-chrome",
            process_counter=lambda: 1,
        )
        result = agent.diagnose(cdp_url="http://127.0.0.1:9222")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["recommendations"], [])

    def test_governed_cli_run_accepts_a_completed_blocker_diagnosis(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main([
                "--json", "run", "diagnose Chrome DevTools connectivity",
                "--capability", "core.chrome_diagnostics", "--trust", "PREPARE", "--execute",
            ])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "passed")


if __name__ == "__main__":
    unittest.main()
