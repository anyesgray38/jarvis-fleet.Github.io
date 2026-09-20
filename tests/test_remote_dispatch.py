import unittest
from unittest.mock import patch
from jarvis.remote_dispatch import submit_issue, RemoteDispatchError

class RemoteDispatchTests(unittest.TestCase):
    @patch("jarvis.remote_dispatch.shutil.which", return_value="gh")
    @patch("jarvis.remote_dispatch.subprocess.run")
    def test_submit_issue_uses_structured_fields(self, run_mock, _which):
        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = "https://github.com/owner/repo/issues/42\n"
        run_mock.return_value.stderr = ""
        result = submit_issue(repository="owner/repo", objective="Improve correlation",
                              ref="master", capability="terminal.execute", job_id="job_abc123")
        self.assertEqual(result["url"], "https://github.com/owner/repo/issues/42")
        command = run_mock.call_args.args[0]
        self.assertEqual(command[:4], ["gh", "issue", "create", "--repo"])
        self.assertNotIn("bash", command)
        self.assertIn("job_abc123", command[-1])
        self.assertIn("Improve correlation", command[-1])

    @patch("jarvis.remote_dispatch.shutil.which", return_value=None)
    def test_requires_gh(self, _which):
        with self.assertRaises(RemoteDispatchError):
            submit_issue(repository="owner/repo", objective="x", ref="master",
                         capability="terminal.execute", job_id="job_abc123")

if __name__ == "__main__":
    unittest.main()
