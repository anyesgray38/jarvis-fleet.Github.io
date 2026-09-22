"""Bounded per-node MCP and LocalAI inventory records."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any, Mapping

from .node import FleetNode

_ITEM_KEYS = {"id", "name", "version", "provider", "capabilities", "modalities"}


class InventoryError(ValueError):
    """Raised when a node inventory is malformed or unsafe to retain."""


def _items(value: Any, field: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or len(value) > 256:
        raise InventoryError(f"{field} must contain at most 256 items")
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping) or not item:
            raise InventoryError(f"{field} entries must be non-empty objects")
        if not set(item).issubset(_ITEM_KEYS):
            raise InventoryError(f"{field} contains an unsupported metadata field")
        clean: dict[str, Any] = {}
        for key, raw in item.items():
            if key in {"id", "name", "version", "provider"}:
                if not isinstance(raw, str) or not raw or len(raw) > 512:
                    raise InventoryError(f"{field}.{key} must be a bounded string")
                clean[key] = raw
            elif key in {"capabilities", "modalities"}:
                if not isinstance(raw, list) or len(raw) > 128 or not all(isinstance(v, str) and v for v in raw):
                    raise InventoryError(f"{field}.{key} must be a bounded string list")
                clean[key] = sorted(set(raw))
        if not clean.get("id") and not clean.get("name"):
            raise InventoryError(f"{field} entries require id or name")
        normalized.append(clean)
    return tuple(sorted(normalized, key=lambda item: (item.get("id", item.get("name", "")), json.dumps(item, sort_keys=True))))


@dataclass(frozen=True)
class NodeInventory:
    node_id: str
    mcp_servers: tuple[dict[str, Any], ...]
    localai_models: tuple[dict[str, Any], ...]
    collected_at: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "mcp_servers": list(self.mcp_servers),
            "localai_models": list(self.localai_models),
            "collected_at": self.collected_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}


def build_inventory(node_id: str, *, mcp_servers: list[Mapping[str, Any]],
                    localai_models: list[Mapping[str, Any]], collected_at: int | None = None) -> NodeInventory:
    if not isinstance(node_id, str) or not node_id:
        raise InventoryError("node_id is required")
    inventory = NodeInventory(node_id=node_id, mcp_servers=_items(mcp_servers, "mcp_servers"),
                              localai_models=_items(localai_models, "localai_models"),
                              collected_at=int(time.time()) if collected_at is None else collected_at,
                              digest="")
    canonical = json.dumps(inventory.payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return NodeInventory(**{**inventory.__dict__, "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest()})


class InventoryRegistry:
    """In-memory registry for the latest verified inventory per node."""

    def __init__(self):
        self._records: dict[str, NodeInventory] = {}

    def record(self, node: FleetNode, inventory: NodeInventory) -> NodeInventory:
        if node.node_id != inventory.node_id:
            raise InventoryError("inventory node_id does not match node")
        if node.trust not in {"trusted", "verified"}:
            raise InventoryError("inventory requires a trusted or verified node")
        rebuilt = build_inventory(inventory.node_id, mcp_servers=list(inventory.mcp_servers),
                                  localai_models=list(inventory.localai_models), collected_at=inventory.collected_at)
        if rebuilt.digest != inventory.digest:
            raise InventoryError("inventory digest does not match contents")
        self._records[node.node_id] = inventory
        return inventory

    def get(self, node_id: str) -> NodeInventory:
        try:
            return self._records[node_id]
        except KeyError as exc:
            raise InventoryError(f"no inventory for node {node_id}") from exc
