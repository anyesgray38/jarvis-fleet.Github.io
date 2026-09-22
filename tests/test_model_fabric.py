import json
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import Mock, patch

from providers.model_fabric import ModelFabric
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
        self.assertEqual(registry.routable_for("localai")[0].provider, "localai")

    def test_router_rejects_unregistered_live_model(self):
        provider = Mock()
        provider.provider_id = "localai"
        provider.models.return_value = [{"id": "unknown-model", "tags": ["general"]}]
        router = ModelRouter([provider], registry=self.registry())
        with self.assertRaises(LookupError):
            router.resolve(request=RoutingRequest(purpose="general"))

    def test_router_requires_model_purpose(self):
        provider = Mock()
        provider.provider_id = "localai"
        provider.models.return_value = [{"id": "google/gemma-4-31B-it"}]
        router = ModelRouter([provider], registry=self.registry())
        route = router.resolve(request=RoutingRequest(purpose="verification"))
        self.assertEqual(route.model, "google/gemma-4-31B-it")

    def test_router_requires_local_model_for_local_only(self):
        provider = Mock()
        provider.provider_id = "localai"
        provider.models.return_value = [{"id": "Qwen/Qwen3.8-Flash-Next"}]
        router = ModelRouter([provider], registry=self.registry())
        route = router.resolve(request=RoutingRequest(local_only=True, purpose="planning"))
        self.assertEqual(route.provider, "localai")

    def test_external_model_requires_explicit_opt_in(self):
        provider = Mock()
        provider.provider_id = "openai"
        provider.models.return_value = [{"id": "gpt-5-mini"}]
        router = ModelRouter([provider], provider_specs={"openai": {"id": "openai", "external": True, "modalities": ["text"]}}, registry=self.registry())
        with self.assertRaises(LookupError):
            router.resolve(request=RoutingRequest(preferred_provider="openai"))
        route = router.resolve(request=RoutingRequest(preferred_provider="openai", allow_external=True, purpose="general"))
        self.assertEqual((route.provider, route.model), ("openai", "gpt-5-mini"))

    def test_openai_provider_is_loaded_only_when_key_is_present(self):
        provider_path = Path(__file__).parents[1] / "capabilities" / "providers.json"
        model_path = Path(__file__).parents[1] / "capabilities" / "models.json"
        with patch.dict(os.environ, {"AEGIS_OPENAI_API_KEY": "test-key"}, clear=False):
            fabric = ModelFabric.from_files(model_registry_path=model_path, provider_registry_path=provider_path)
        self.assertEqual({provider.provider_id for provider in fabric.providers}, {"localai", "ollama", "openai"})

    def test_ollama_provider_is_loaded_from_local_endpoint(self):
        provider_path = Path(__file__).parents[1] / "capabilities" / "providers.json"
        model_path = Path(__file__).parents[1] / "capabilities" / "models.json"
        fabric = ModelFabric.from_files(
            model_registry_path=model_path,
            provider_registry_path=provider_path,
            ollama_url="http://127.0.0.1:11434",
        )
        self.assertEqual({provider.provider_id for provider in fabric.providers}, {"localai", "ollama"})

    def test_registry_rejects_duplicate_ids(self):
        payload = {"version": 1, "models": [{"id": "x", "provider": "p"}, {"id": "x", "provider": "p"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as handle:
            json.dump(payload, handle)
            handle.flush()
            with self.assertRaises(ValueError):
                ModelRegistry.from_file(handle.name)


if __name__ == "__main__":
    unittest.main()
