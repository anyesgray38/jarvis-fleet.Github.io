"""Capability discovery and policy boundary for the Jarvis fleet."""
import json
from pathlib import Path
from typing import Any


class CapabilityRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data = json.loads(self.path.read_text(encoding="utf-8"))
        self._capabilities = {c["id"]: c for c in self._data["capabilities"]}

    def get(self, capability_id: str) -> dict[str, Any]:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise ValueError(f"unknown capability: {capability_id}") from exc

    def list(self) -> list[dict[str, Any]]:
        return list(self._capabilities.values())

    def compatible(self, capability_id: str, agent_tags: set[str]) -> bool:
        capability = self.get(capability_id)
        return bool(set(capability.get("tags", [])) & agent_tags)
