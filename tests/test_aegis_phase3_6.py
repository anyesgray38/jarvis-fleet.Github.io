import unittest

from jarvis.verification import evidence_digest, verify_inference_response


class AegisPhase36Tests(unittest.TestCase):
    def test_valid_response_verifies(self):
        result = verify_inference_response({"content": "AEGIS online"})
        self.assertTrue(result["verified"])
        self.assertTrue(all(result["checks"].values()))

    def test_empty_response_fails(self):
        result = verify_inference_response({"content": "   "})
        self.assertFalse(result["verified"])
        self.assertFalse(result["checks"]["content_nonempty"])

    def test_evidence_digest_changes_with_record_and_chain(self):
        first = evidence_digest({"request_id": "a", "response": {"content": "one"}})
        second = evidence_digest({"request_id": "a", "response": {"content": "one"}}, first)
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
