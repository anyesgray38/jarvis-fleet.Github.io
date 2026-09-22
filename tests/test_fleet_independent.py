import unittest

from fleet import FleetNode, IndependentVerifier, RequestSigner, SignedRemoteTransport


class FleetIndependentVerificationTests(unittest.TestCase):
    def test_verified_distinct_node_can_verify_artifact(self):
        verifier_signer = RequestSigner("secret", "verifier-1")

        def sender(node, request):
            payload = request["body"]["payload"]
            artifact = payload["artifact"]
            return verifier_signer.sign({
                "verified": True,
                "task_id": payload["task_id"],
                "artifact_digest": payload["artifact_digest"],
                "observed_keys": sorted(artifact),
            }, request_id=request["request_id"], timestamp=100).to_dict()

        transport = SignedRemoteTransport("secret", sender=sender)
        result = IndependentVerifier(transport).verify(
            execution_node=FleetNode("worker-1", trust="verified", status="connected"),
            verifier_node=FleetNode("verifier-1", trust="verified", status="connected"),
            task_id="task-1", artifact={"result": "ok"}, request_id="verify-1", timestamp=100, now=100,
        )
        self.assertTrue(result.verified)

    def test_same_or_unverified_node_is_rejected(self):
        transport = SignedRemoteTransport("secret", sender=lambda *_: {})
        same = FleetNode("worker-1", trust="verified", status="connected")
        result = IndependentVerifier(transport).verify(
            execution_node=same, verifier_node=same, task_id="task-1", artifact={}, request_id="verify-1", now=100,
        )
        self.assertFalse(result.verified)
        result = IndependentVerifier(transport).verify(
            execution_node=same, verifier_node=FleetNode("verifier-1", trust="trusted", status="connected"),
            task_id="task-1", artifact={}, request_id="verify-2", now=100,
        )
        self.assertFalse(result.verified)


if __name__ == "__main__":
    unittest.main()
