import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from providers.model_registry import ModelRegistry
from providers.model_router import ModelRouter
from providers.routing_policy import RoutingRequest


class ModelFabricTests(unittest.TestCase):
    def registry(self):
        path = Path(__file__).parents[1] / "capabilities" / "models.json"
        return ModelRegistry.from_file(path)

    def test_registry_loads_models(self):
        registry = self.registry()
        self.assertIsNotNone(registry.get("Qwen/Qwen3.8-Flash-Next"))
        self.assertIsNotNone(registry.get("google/gemma-4-31B-it"))
        self.assertEqual(registry.routable_for("lmstudio")[0].provider, "lmstudio")

    def test_non_routable_dataset_is_not_admitted(self):
        registry = self.registry()
        self.assertEqual(registry.candidate_map("none"), {})
        self.assertFalse(registry.get("lmstudio/qwen3.8-max-glm5.2-kimi-k3-distillation").routable)

    def test_router_rejects_unregistered_live_model(self):
        provider = Mock()
        provider.provider_id = "lmstudio"
        provider.models.return_value = [{"id": "unknown-model", "tags": ["general"]}]
        router = ModelRouter([provider], registry=self.registry())
        with self.assertRaises(LookupError):
            router.resolve(request=RoutingRequest(purpose="general"))

    def test_router_requires_model_purpose(self):
        provider = Mock()
        provider.provider_id = "lmstudio"
        provider.models.return_value = [{"id": "google/gemma-4-31B-it"}]
        router = ModelRouter([provider], registry=self.registry())
        route = router.resolve(request=RoutingRequest(purpose="verification"))
        self.assertEqual(route.model, "google/gemma-4-31B-it")

    def test_router_requires_local_model_for_local_only(self):
        provider = Mock()
        provider.provider_id = "lmstudio"
        provider.models.return_value = [{"id": "Qwen/Qwen3.8-Flash-Next"}]
        router = ModelRouter([provider], registry=self.registry())
        route = router.resolve(request=RoutingRequest(local_only=True, purpose="planning"))
        self.assertEqual(route.provider, "lmstudio")

    def test_registry_rejects_duplicate_ids(self):
        payload = {"version": 1, "models": [{"id": "x", "provider": "p"}, {"id": "x", "provider": "p"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(payload, handle)
            handle.flush()
            with self.assertRaises(ValueError):
                ModelRegistry.from_file(handle.name)


if __name__ == "__main__":
    unittest.main()
