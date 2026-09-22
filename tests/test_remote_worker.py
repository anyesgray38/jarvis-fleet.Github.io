import tempfile
import unittest
from pathlib import Path

from jarvis.remote_worker import apply_patch, validate_patch, ensure_clean


class RemoteWorkerSafetyTests(unittest.TestCase):
    def test_rejects_binary_patch(self):
        with self.assertRaises(RuntimeError):
            validate_patch("diff --git a/app.py b/app.py\nGIT binary patch")

    def test_rejects_protected_workflow(self):
        patch = "diff --git a/.github/workflows/publish.yml b/.github/workflows/publish.yml\n"
        with self.assertRaises(RuntimeError):
            validate_patch(patch)

    def test_accepts_normal_source_patch(self):
        validate_patch("diff --git a/app.py b/app.py\n")

    def test_requires_clean_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".git").mkdir()
            with self.assertRaises(RuntimeError):
                ensure_clean(project)

    def test_apply_patch_rejects_protected_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            with self.assertRaises(RuntimeError):
                apply_patch(project, "diff --git a/.env b/.env\n")


if __name__ == "__main__":
    unittest.main()
