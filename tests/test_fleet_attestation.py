import unittest

from fleet import AttestationAuthority, AttestationError, FleetNode, RequestSigner, create_attestation


class FleetAttestationTests(unittest.TestCase):
    def test_valid_attestation_promotes_node(self):
        signer = RequestSigner("secret", "worker-1")
        attestation = create_attestation(signer, capabilities=["coding"], modalities=["text"],
                                         inventory_digest="a" * 64, request_id="attest-1", timestamp=100)
        node = FleetNode("worker-1", trust="untrusted", status="connected")
        verified = AttestationAuthority("secret").accept(node, attestation, now=100)
        self.assertEqual(verified.trust, "verified")
        self.assertEqual(verified.capabilities, frozenset({"coding"}))
        self.assertEqual(verified.metadata["attestation"], "verified")

    def test_attestation_cannot_promote_another_node(self):
        attestation = create_attestation(RequestSigner("secret", "worker-1"), capabilities=[], modalities=[],
                                         inventory_digest="a" * 64, request_id="attest-1", timestamp=100)
        with self.assertRaises(AttestationError):
            AttestationAuthority("secret").accept(FleetNode("worker-2", status="connected"), attestation, now=100)

    def test_invalid_inventory_digest_is_rejected(self):
        with self.assertRaises(AttestationError):
            create_attestation(RequestSigner("secret", "worker-1"), capabilities=[], modalities=[],
                               inventory_digest="not-a-digest", request_id="attest-1", timestamp=100)


if __name__ == "__main__":
    unittest.main()
