"""Provider-neutral, task-aware model routing for AEGIS."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol
from .routing_policy import CandidateScore, RoutingRequest, score_candidate

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
    score: float = 0.0
    fallback_providers: tuple[str, ...] = ()

class ModelRouter:
    """Select the best compatible approved model using explicit routing policy."""
    def __init__(self, providers: list[ModelProvider], provider_specs: dict[str, dict[str, Any]] | None = None):
        self.providers = {p.provider_id: p for p in providers}
        self.provider_specs = provider_specs or {}

    def rank(self, request: RoutingRequest) -> list[CandidateScore]:
        ranked: list[CandidateScore] = []
        for provider in self.providers.values():
            spec = {"id": provider.provider_id, "external": False, "modalities": ["text"]}
            spec.update(self.provider_specs.get(provider.provider_id, {}))
            for model in provider.models():
                candidate = score_candidate(spec, model, request)
                if candidate:
                    ranked.append(candidate)
        return sorted(ranked, key=lambda c: (-c.score, c.provider, c.model))

    def resolve(self, *, preferred_provider: str | None = None,
                required_tags: set[str] | None = None,
                request: RoutingRequest | None = None) -> ModelRoute:
        request = request or RoutingRequest(
            preferred_provider=preferred_provider,
            required_tags=frozenset(required_tags or set()),
        )
        ranked = self.rank(request)
        if not ranked:
            raise LookupError("No approved model satisfies the requested routing constraints")
        winner = ranked[0]
        fallbacks = tuple(dict.fromkeys(c.provider for c in ranked[1:] if c.provider != winner.provider))
        return ModelRoute(
            provider=winner.provider,
            model=winner.model,
            reason="; ".join(winner.reasons) or "highest compatible policy score",
            constraints={"modality": request.modality, "purpose": request.purpose, "local_only": request.local_only},
            score=winner.score,
            fallback_providers=fallbacks,
        )

    def chat(self, route: ModelRoute, *, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        provider = self.providers.get(route.provider)
        if provider is None:
            raise LookupError(f"Unknown model provider: {route.provider}")
        return provider.chat(model=route.model, messages=messages, **kwargs)
