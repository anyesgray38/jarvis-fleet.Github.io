import unittest
from types import SimpleNamespace
from fleet import FleetNode, HealthSnapshot, TailscaleHealthProvider

class FleetHealthTests(unittest.TestCase):
    def test_unreachable_node_is_unhealthy(self):
        self.assertFalse(HealthSnapshot(reachable=False).healthy)
        self.assertEqual(HealthSnapshot(reachable=False).score(), 0.0)

    def test_stale_node_is_unhealthy(self):
        self.assertFalse(HealthSnapshot(reachable=True, last_seen_age_s=121).healthy)

    def test_healthy_node_scores_positive(self):
        snapshot = HealthSnapshot(reachable=True, latency_ms=20, load=0.2, last_seen_age_s=5)
        self.assertTrue(snapshot.healthy)
        self.assertGreater(snapshot.score(), 0)

    def test_tailscale_provider_maps_online_peer(self):
        result = SimpleNamespace(returncode=0, stdout='{"Peer":{"peer-id":{"ID":"peer-id","HostName":"worker","TailscaleIPs":["100.64.0.2"],"Online":true,"LatencyMS":12.5}}}', stderr="")
        provider = TailscaleHealthProvider(runner=lambda *args, **kwargs: result)
        snapshot = provider.snapshot(FleetNode("worker", address="100.64.0.2"), now=100)
        self.assertTrue(snapshot.healthy)
        self.assertEqual(snapshot.latency_ms, 12.5)

    def test_tailscale_provider_marks_missing_peer_unreachable(self):
        result = SimpleNamespace(returncode=0, stdout='{"Peer":{}}', stderr="")
        provider = TailscaleHealthProvider(runner=lambda *args, **kwargs: result)
        self.assertFalse(provider.snapshot(FleetNode("missing"), now=100).reachable)

if __name__ == "__main__":
    unittest.main()
