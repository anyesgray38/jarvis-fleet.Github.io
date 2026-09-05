"""Task-aware model routing policy for AEGIS."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RoutingRequest:
    required_tags: frozenset[str] = frozenset()
    modality: str = "text"
    preferred_provider: str | None = None
    local_only: bool = False
    allow_external: bool = False
    max_latency_ms: int | None = None
    max_cost_per_1k_tokens: float | None = None
    purpose: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateScore:
    provider: str
    model: str
    score: float
    reasons: tuple[str, ...]


def score_candidate(provider: dict[str, Any], model: dict[str, Any], request: RoutingRequest) -> CandidateScore | None:
    policy = provider.get("policy", {})
    provider_modalities = set(provider.get("modalities", []))
    model_modalities = set(model.get("modalities", []))
    if request.modality not in provider_modalities:
        return None
    if model_modalities and request.modality not in model_modalities:
        return None
    if not request.required_tags <= set(model.get("tags", [])):
        return None
    purposes = set(model.get("purposes", []))
    if purposes and request.purpose not in purposes:
        return None
    if request.preferred_provider and provider.get("id") != request.preferred_provider:
        return None
    if request.local_only and (provider.get("external", False) or not model.get("local_only", False)):
        return None
    if not request.allow_external and provider.get("external", False):
        return None
    if model.get("routable", True) is not True:
        return None
    latency = model.get("latency_ms")
    cost = model.get("cost_per_1k_tokens")
    if request.max_latency_ms is not None and latency is not None and latency > request.max_latency_ms:
        return None
    if request.max_cost_per_1k_tokens is not None and cost is not None and cost > request.max_cost_per_1k_tokens:
        return None
    score = 0.0
    reasons: list[str] = []
    if policy.get("local_preferred") and not provider.get("external", False):
        score += 100
        reasons.append("local provider preferred")
    if request.preferred_provider:
        score += 200
        reasons.append("explicit provider preference")
    if request.local_only:
        score += 200
        reasons.append("local-only task")
    if request.purpose in {"verification", "security", "audit"} and not provider.get("external", False):
        score += 50
        reasons.append("sensitive purpose favors local execution")
    if model.get("experimental"):
        score -= 10
        reasons.append("experimental model penalty")
    if latency is not None:
        score += max(0.0, 25.0 - latency / 100.0)
    if cost is not None:
        score += max(0.0, 25.0 - cost * 100.0)
    return CandidateScore(provider["id"], model["id"], score, tuple(reasons))
