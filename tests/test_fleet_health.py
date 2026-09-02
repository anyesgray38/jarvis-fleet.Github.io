import unittest
from fleet.health import HealthSnapshot

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

if __name__ == "__main__":
    unittest.main()
