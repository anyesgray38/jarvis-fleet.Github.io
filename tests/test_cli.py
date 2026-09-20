import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from jarvis.cli import BANNER, build_parser, main


class CliTests(unittest.TestCase):
    def test_parser_exposes_control_plane_commands(self):
        parser = build_parser()
        for command in ("status", "ask", "run", "plan", "simulate", "inspect", "safety", "toggle", "capabilities", "agents", "providers", "logs", "memory", "doctor"):
            argv = [command] + (["x"] if command in {"ask", "inspect", "plan", "simulate"} else [])
            if command == "run":
                argv += ["x", "--capability", "core.task_orchestration"]
            args = parser.parse_args(argv)
            self.assertEqual(args.command, command)

    def test_help_contains_aegis_banner(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["help"]), 0)
        self.assertIn("A E G I S", output.getvalue())
        self.assertIn("AI EXECUTE", output.getvalue())
        self.assertIn(BANNER.splitlines()[1].strip(), output.getvalue())

    def test_json_status_and_safety_toggle(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = str(Path(tmp) / "safety.json")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--json", "--safety-config", config, "status"]), 0)
            self.assertIn('"system": "AEGIS"', output.getvalue())

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--safety-config", config, "toggle", "shell_execution", "on"]), 0)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--json", "--safety-config", config, "safety", "show", "shell_execution"]), 0)
            self.assertIn('"shell_execution": true', output.getvalue())

    def test_simulate_is_non_executing(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["simulate", "test", "--capability", "shell.execute", "--trust", "EXECUTE_LOCAL"]), 0)
        self.assertIn("would_execute", output.getvalue())


if __name__ == "__main__":
    unittest.main()
