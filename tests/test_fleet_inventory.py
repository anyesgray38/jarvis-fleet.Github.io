import unittest

from fleet import FleetNode, InventoryError, InventoryRegistry, build_inventory


class FleetInventoryTests(unittest.TestCase):
    def test_inventory_digest_is_deterministic_and_registry_accepts_verified_node(self):
        inventory = build_inventory("worker-1", mcp_servers=[{"name": "browser", "version": "1"}],
                                    localai_models=[{"id": "qwen", "provider": "localai"}], collected_at=100)
        same = build_inventory("worker-1", mcp_servers=[{"version": "1", "name": "browser"}],
                               localai_models=[{"provider": "localai", "id": "qwen"}], collected_at=100)
        self.assertEqual(inventory.digest, same.digest)
        registry = InventoryRegistry()
        node = FleetNode("worker-1", trust="verified")
        self.assertIs(registry.record(node, inventory), inventory)
        self.assertEqual(registry.get("worker-1").digest, inventory.digest)

    def test_untrusted_node_cannot_publish_inventory(self):
        inventory = build_inventory("worker-1", mcp_servers=[], localai_models=[], collected_at=100)
        with self.assertRaises(InventoryError):
            InventoryRegistry().record(FleetNode("worker-1", trust="untrusted"), inventory)

    def test_sensitive_or_unbounded_metadata_is_rejected(self):
        with self.assertRaises(InventoryError):
            build_inventory("worker-1", mcp_servers=[{"endpoint": "http://secret"}], localai_models=[])


if __name__ == "__main__":
    unittest.main()
