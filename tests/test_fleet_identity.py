import unittest

from fleet.enrollment import EnrollmentAuthority, EnrollmentDenied, EnrollmentRequest
from fleet.identity import sign_request, verify_request
from fleet.transport import ExecutionRequest, SignedTransport


class FleetIdentityTests(unittest.TestCase):
    def test_enrollment_starts_untrusted(self):
        authority = EnrollmentAuthority("bootstrap-secret")
        identity = authority.enroll(EnrollmentRequest("node-1", "worker", "bootstrap-secret"))
        self.assertEqual(identity.trust, "untrusted")
        self.assertTrue(identity.key_id)

    def test_invalid_enrollment_is_denied(self):
        authority = EnrollmentAuthority("bootstrap-secret")
        with self.assertRaises(EnrollmentDenied):
            authority.enroll(EnrollmentRequest("node-1", "worker", "wrong"))

    def test_signature_requires_fresh_valid_envelope(self):
        envelope = sign_request(b"secret", node_id="node-1", request_id="req-1", payload={"x": 1}, timestamp=100)
        self.assertTrue(verify_request(b"secret", envelope, now=120, max_age_seconds=30))
        self.assertFalse(verify_request(b"wrong", envelope, now=120, max_age_seconds=30))
        self.assertFalse(verify_request(b"secret", envelope, now=200, max_age_seconds=30))

    def test_transport_signs_before_send(self):
        captured = {}
        def send(envelope):
            captured.update(envelope)
            return {"accepted": True}
        transport = SignedTransport(node_id="node-1", secret=b"secret", send=send)
        result = transport.dispatch(ExecutionRequest("task-1", "core.mcp_execution", {}, {"required": True}))
        self.assertTrue(result["accepted"])
        self.assertTrue(verify_request(b"secret", captured, max_age_seconds=60))


if __name__ == "__main__":
    unittest.main()
