import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from actions.fabric import ActionContext, default_fabric
from jarvis.cli import main
from security.safety import SafetySettings, control_for_capability


class TerminalControlTests(unittest.TestCase):
    def test_terminal_capabilities_are_safety_gated(self):
        self.assertEqual(control_for_capability("terminal.execute"), "terminal_execution")
        self.assertEqual(control_for_capability("terminal.write"), "terminal_execution")

    def test_shell_action_is_registered_but_requires_safety_gate(self):
        fabric = default_fabric()
        self.assertIn("shell.execute", fabric.available())

    def test_exec_requires_terminal_safety_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = str(Path(tmp) / "safety.json")
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main([
                    "--safety-config", config,
                    "exec", "python3", "-c", "print('AEGIS_TEST')"
                ])
            self.assertEqual(rc, 0)
            self.assertIn("terminal_execution", output.getvalue())
            self.assertIn("rejected", output.getvalue())

    def test_audit_is_compile_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text("print('ok')\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["--json", "audit", str(path)])
            self.assertEqual(rc, 0)
            payload = json.loads(output.getvalue())
            self.assertTrue(payload["syntax_ok"])
            self.assertEqual(payload["mode"], "compile_only")


if __name__ == "__main__":
    unittest.main()
