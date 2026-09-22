import unittest

from fleet import EnrollmentAuthority, FleetAuthError, RequestSigner, RequestVerifier


class FleetAuthTests(unittest.TestCase):
    def test_enrollment_starts_untrusted(self):
        request = RequestSigner("bootstrap", "node-1").sign(
            {"network": "tailscale", "address": "100.64.0.2", "capabilities": ["coding"], "modalities": ["text"], "labels": ["linux"]},
            request_id="enroll-1", timestamp=100,
        )
        node = EnrollmentAuthority("bootstrap").enroll(request, now=100)
        self.assertEqual(node.trust, "untrusted")
        self.assertEqual(node.metadata["attestation"], "pending")

    def test_enrollment_rejects_non_tailscale(self):
        request = RequestSigner("bootstrap", "node-1").sign(
            {"network": "internet"}, request_id="enroll-1", timestamp=100,
        )
        with self.assertRaises(FleetAuthError):
            EnrollmentAuthority("bootstrap").enroll(request, now=100)

    def test_signed_request_is_verified_once(self):
        request = RequestSigner("secret", "node-1").sign(
            {"capability": "health"}, request_id="request-1", timestamp=100,
        )
        verifier = RequestVerifier("secret", expected_node_id="node-1")
        self.assertEqual(verifier.verify(request, now=100), {"capability": "health"})
        with self.assertRaises(FleetAuthError):
            verifier.verify(request, now=100)

    def test_tampering_and_stale_requests_are_rejected(self):
        request = RequestSigner("secret", "node-1").sign(
            {"capability": "health"}, request_id="request-1", timestamp=100,
        )
        verifier = RequestVerifier("secret", max_age_seconds=60)
        tampered = {**request.to_dict(), "body": {"capability": "shell"}}
        with self.assertRaises(FleetAuthError):
            verifier.verify(tampered, now=100)
        with self.assertRaises(FleetAuthError):
            verifier.verify(request, now=161)


if __name__ == "__main__":
    unittest.main()
