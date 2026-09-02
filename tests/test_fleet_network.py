import unittest
from fleet import FleetNode, FleetScheduler, NetworkPolicy, NetworkPolicyDenied, NetworkRequest, Workload

class FleetNetworkTests(unittest.TestCase):
    def test_tailscale_verified_node_is_preferred(self):
        nodes = [
            FleetNode("internet-worker", network="internet", status="ready", trust="verified", capabilities=frozenset({"research"})),
            FleetNode("overlay-worker", network="tailscale", status="connected", trust="verified", capabilities=frozenset({"research"})),
        ]
        self.assertEqual(FleetScheduler(nodes).resolve(Workload("research")).node_id, "overlay-worker")

    def test_untrusted_node_is_rejected(self):
        node = FleetNode("unknown", status="connected", trust="untrusted")
        with self.assertRaises(NetworkPolicyDenied):
            NetworkPolicy().authorize(NetworkRequest(private_network=True), node=node)

    def test_public_bind_is_fail_closed(self):
        with self.assertRaises(NetworkPolicyDenied):
            NetworkPolicy().authorize(NetworkRequest(public_bind=True))

    def test_missing_capability_cannot_schedule(self):
        node = FleetNode("worker", status="ready", trust="verified", capabilities=frozenset({"coding"}))
        with self.assertRaises(LookupError):
            FleetScheduler([node]).resolve(Workload("research"))

if __name__ == "__main__":
    unittest.main()
