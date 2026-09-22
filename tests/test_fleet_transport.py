import unittest

from fleet import FleetNode, FleetTransportError, RequestSigner, SignedRemoteTransport


class FleetTransportTests(unittest.TestCase):
    def test_signed_execution_round_trip(self):
        captured = {}
        worker_signer = RequestSigner("secret", "worker-1")

        def sender(node, request):
            captured.update(request)
            return worker_signer.sign({"ok": True, "result": "done"},
                                      request_id=request["request_id"], timestamp=100).to_dict()

        transport = SignedRemoteTransport("secret", sender=sender)
        result = transport.execute(
            FleetNode("worker-1", network="tailscale", status="connected", trust="verified"),
            "health.check", {"verbose": True}, request_id="request-1", timestamp=100, now=100,
        )
        self.assertEqual(result["result"], "done")
        self.assertEqual(captured["body"]["operation"], "health.check")

    def test_untrusted_node_is_rejected_before_send(self):
        transport = SignedRemoteTransport("secret", sender=lambda *_: {})
        with self.assertRaises(FleetTransportError):
            transport.execute(FleetNode("worker-1", status="connected", trust="untrusted"),
                              "health.check", {}, request_id="request-1", timestamp=100, now=100)

    def test_mismatched_response_is_rejected(self):
        worker_signer = RequestSigner("secret", "worker-1")

        def sender(node, request):
            return worker_signer.sign({"ok": True}, request_id="different", timestamp=100).to_dict()

        transport = SignedRemoteTransport("secret", sender=sender)
        with self.assertRaises(FleetTransportError):
            transport.execute(FleetNode("worker-1", status="connected", trust="trusted"),
                              "health.check", {}, request_id="request-1", timestamp=100, now=100)


if __name__ == "__main__":
    unittest.main()
