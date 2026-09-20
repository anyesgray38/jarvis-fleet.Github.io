import tempfile
import unittest
from pathlib import Path
from jarvis.cli import build_parser, execute

class ProjectCliTests(unittest.TestCase):
    def test_project_start_parser_and_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            args = build_parser().parse_args([
                "project", "start", "Improve timeframe correlation",
                "--repository", "owner/repo", "--db", str(db), "--no-dispatch"
            ])
            self.assertEqual(args.command, "project")
            self.assertEqual(args.project_command, "start")
            self.assertEqual(execute(args), 0)

            status = build_parser().parse_args([
                "project", "status", "--db", str(db)
            ])
            self.assertEqual(execute(status), 0)

if __name__ == "__main__":
    unittest.main()
