import unittest

from fleet import FleetEvidenceChain, FleetEvidenceError


class FleetEvidenceTests(unittest.TestCase):
    def test_records_correlate_and_chain(self):
        chain = FleetEvidenceChain()
        first = chain.append(node_id="worker-1", task_id="task-1", tool="mcp.browser",
                             model="localai/qwen", payload={"ok": True}, event_id="event-1", timestamp="t1")
        second = chain.append(node_id="worker-1", task_id="task-1", tool="mcp.browser",
                              model="localai/qwen", payload={"result": "done"}, event_id="event-2", timestamp="t2")
        self.assertEqual(second.record["previous_digest"], first.digest)
        self.assertTrue(FleetEvidenceChain.verify(first.record))
        self.assertTrue(FleetEvidenceChain.verify(second.record))

    def test_tampering_breaks_verification(self):
        record = FleetEvidenceChain().append(node_id="worker-1", task_id="task-1", tool="tool",
                                              model="model", payload={"ok": True}).to_dict()
        record["payload"] = {"ok": False}
        self.assertFalse(FleetEvidenceChain.verify(record))

    def test_labels_are_required(self):
        with self.assertRaises(FleetEvidenceError):
            FleetEvidenceChain().append(node_id="", task_id="task-1", tool="tool", model="model", payload={})


if __name__ == "__main__":
    unittest.main()
