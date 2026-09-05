"""Assemble the governed AEGIS model fabric from checked-in policy."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .localai import LocalAIConfig, LocalAIProvider
from .model_registry import ModelRegistry
from .model_router import ModelRouter
from .openai_compatible import OpenAICompatibleConfig, OpenAICompatibleProvider


class ModelFabric:
    """Runtime facade joining provider discovery, registry admission, and routing."""

    def __init__(self, registry: ModelRegistry, providers: list[Any], provider_specs: dict[str, dict[str, Any]]):
        self.registry = registry
        self.providers = providers
        self.router = ModelRouter(providers, provider_specs=provider_specs, registry=registry)

    @classmethod
    def from_files(
        cls,
        *,
        model_registry_path: str | Path,
        provider_registry_path: str | Path,
        localai_url: str = "http://127.0.0.1:8080",
        lmstudio_url: str = "http://127.0.0.1:1234",
        timeout: float = 120.0,
    ) -> "ModelFabric":
        registry = ModelRegistry.from_file(model_registry_path)
        payload = json.loads(Path(provider_registry_path).read_text(encoding="utf-8"))
        providers: list[Any] = []
        specs: dict[str, dict[str, Any]] = {}
        for spec in payload.get("providers", []):
            provider_id = spec.get("id")
            if not isinstance(provider_id, str):
                continue
            specs[provider_id] = spec
            if provider_id == "localai":
                providers.append(LocalAIProvider(LocalAIConfig(base_url=localai_url, timeout=timeout)))
            elif provider_id == "lmstudio":
                providers.append(OpenAICompatibleProvider(
                    provider_id="lmstudio",
                    config=OpenAICompatibleConfig(base_url=lmstudio_url, timeout=timeout),
                ))
        return cls(registry, providers, specs)

    def resolve(self, **kwargs: Any):
        return self.router.resolve(**kwargs)

    def chat(self, route, *, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        return self.router.chat(route, messages=messages, **kwargs)
