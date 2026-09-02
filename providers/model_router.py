"""Provider-neutral model routing primitives for AEGIS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ModelProvider(Protocol):
    provider_id: str

    def models(self) -> list[dict[str, Any]]: ...

    def chat(self, *, model: str, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    reason: str
    constraints: dict[str, Any] = field(default_factory=dict)


class ModelRouter:
    """Selects an approved provider without embedding provider logic in AEGIS."""

    def __init__(self, providers: list[ModelProvider]) -> None:
        self.providers = {provider.provider_id: provider for provider in providers}

    def resolve(self, *, preferred_provider: str | None = None,
                required_tags: set[str] | None = None) -> ModelRoute:
        required_tags = required_tags or set()
        candidates: list[tuple[ModelProvider, dict[str, Any]]] = []

        for provider in self.providers.values():
            if preferred_provider and provider.provider_id != preferred_provider:
                continue
            for model in provider.models():
                tags = set(model.get("tags", [])) if isinstance(model, dict) else set()
                if required_tags <= tags:
                    candidates.append((provider, model))

        if not candidates:
            raise LookupError("No approved model provider satisfies the requested constraints")

        provider, model = candidates[0]
        model_id = model.get("id")
        if not model_id:
            raise LookupError(f"Provider {provider.provider_id} returned a model without an id")
        return ModelRoute(provider=provider.provider_id, model=model_id,
                          reason="first compatible approved provider")

    def chat(self, route: ModelRoute, *, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        provider = self.providers.get(route.provider)
        if provider is None:
            raise LookupError(f"Unknown model provider: {route.provider}")
        return provider.chat(model=route.model, messages=messages, **kwargs)
