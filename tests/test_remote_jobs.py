import tempfile
import unittest
from pathlib import Path
from jarvis.remote_jobs import JobStore

class RemoteJobStoreTests(unittest.TestCase):
    def test_job_lifecycle_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            store = JobStore(db)
            created = store.create("test objective", "anyesgray38/jarvis-fleet.Github.io",
                                   input={"command": "echo test"})
            self.assertEqual(created.status, "queued")
            claimed = store.claim("worker-1")
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed.worker, "worker-1")
            self.assertEqual(store.transition(claimed.job_id, "running").status, "running")
            passed = store.transition(claimed.job_id, "passed", result={"returncode": 0})
            self.assertEqual(passed.result["returncode"], 0)
            reopened = JobStore(db)
            self.assertEqual(reopened.get(claimed.job_id).status, "passed")
            self.assertEqual([e["event"] for e in reopened.events(claimed.job_id)],
                             ["job.queued", "job.claimed", "job.running", "job.passed"])

    def test_claim_is_single_consumer(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs.db")
            store.create("objective", "owner/repo")
            self.assertIsNotNone(store.claim("worker-a"))
            self.assertIsNone(store.claim("worker-b"))

if __name__ == "__main__":
    unittest.main()
