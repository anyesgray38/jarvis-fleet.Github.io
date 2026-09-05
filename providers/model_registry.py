"""Authoritative AEGIS model registry for governed inference routing."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ModelRegistryError(ValueError):
    """Raised when the model registry is invalid or cannot be loaded."""


@dataclass(frozen=True)
class RegisteredModel:
    id: str
    provider: str
    modalities: frozenset[str]
    tags: frozenset[str]
    purposes: frozenset[str]
    local_only: bool = False
    experimental: bool = False
    routable: bool = True
    metadata: dict[str, Any] | None = None

    def as_candidate(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tags": sorted(self.tags),
            "modalities": sorted(self.modalities),
            "purposes": sorted(self.purposes),
            "local_only": self.local_only,
            "experimental": self.experimental,
            "routable": self.routable,
            **(self.metadata or {}),
        }


class ModelRegistry:
    """Load and validate the checked-in AEGIS model policy."""

    def __init__(self, models: list[RegisteredModel]) -> None:
        self._models = tuple(models)
        self._by_id = {model.id: model for model in models}

    @classmethod
    def from_file(cls, path: str | Path) -> "ModelRegistry":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"Unable to load model registry: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise ModelRegistryError("Model registry must contain a models list")

        models: list[RegisteredModel] = []
        seen: set[str] = set()
        for raw in payload["models"]:
            if not isinstance(raw, dict):
                raise ModelRegistryError("Every model entry must be an object")
            model_id = raw.get("id")
            provider = raw.get("provider")
            if not isinstance(model_id, str) or not model_id.strip():
                raise ModelRegistryError("Every model requires a non-empty id")
            if model_id in seen:
                raise ModelRegistryError(f"Duplicate model id: {model_id}")
            if not isinstance(provider, str) or not provider.strip():
                raise ModelRegistryError(f"Model {model_id} requires a provider")
            seen.add(model_id)
            routable = raw.get("routable", True)
            if not isinstance(routable, bool):
                raise ModelRegistryError(f"Model {model_id} has invalid routable value")
            models.append(
                RegisteredModel(
                    id=model_id,
                    provider=provider,
                    modalities=frozenset(raw.get("modalities", [])),
                    tags=frozenset(raw.get("tags", [])),
                    purposes=frozenset(raw.get("purposes", [])),
                    local_only=bool(raw.get("local_only", False)),
                    experimental=bool(raw.get("experimental", False)),
                    routable=routable,
                    metadata={k: v for k, v in raw.items() if k not in {
                        "id", "provider", "modalities", "tags", "purposes",
                        "local_only", "experimental", "routable",
                    }},
                )
            )
        return cls(models)

    def all(self) -> tuple[RegisteredModel, ...]:
        return self._models

    def get(self, model_id: str) -> RegisteredModel | None:
        return self._by_id.get(model_id)

    def routable_for(self, provider: str) -> list[RegisteredModel]:
        return [m for m in self._models if m.provider == provider and m.routable]

    def candidate_map(self, provider: str) -> dict[str, RegisteredModel]:
        return {m.id: m for m in self.routable_for(provider)}
