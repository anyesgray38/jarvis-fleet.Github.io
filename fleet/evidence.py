"""Correlated, chained evidence records for distributed Fleet work."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
from typing import Any, Mapping

from jarvis.verification import evidence_digest


class FleetEvidenceError(ValueError):
    """Raised when correlated Fleet evidence is invalid."""


def _label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise FleetEvidenceError(f"{field} must be a bounded non-empty string")
    return value


@dataclass(frozen=True)
class FleetEvidenceRecord:
    record: dict[str, Any]

    @property
    def digest(self) -> str:
        return str(self.record["evidence_digest"])

    def to_dict(self) -> dict[str, Any]:
        return dict(self.record)


class FleetEvidenceChain:
    """Create and verify a local hash chain of cross-node evidence."""

    def __init__(self, *, previous_digest: str = ""):
        self.previous_digest = previous_digest

    def append(self, *, node_id: str, task_id: str, tool: str, model: str,
               payload: Mapping[str, Any], event_id: str | None = None,
               timestamp: str | None = None) -> FleetEvidenceRecord:
        for value, field in ((node_id, "node_id"), (task_id, "task_id"), (tool, "tool"), (model, "model")):
            _label(value, field)
        if not isinstance(payload, Mapping):
            raise FleetEvidenceError("payload must be an object")
        record = {
            "schema": "aegis.fleet.evidence.v1",
            "event_id": event_id or uuid.uuid4().hex,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "node_id": node_id,
            "task_id": task_id,
            "tool": tool,
            "model": model,
            "payload": dict(payload),
            "previous_digest": self.previous_digest,
        }
        digest = evidence_digest(record, self.previous_digest)
        record["evidence_digest"] = digest
        self.previous_digest = digest
        return FleetEvidenceRecord(record)

    @staticmethod
    def verify(record: Mapping[str, Any], *, previous_digest: str | None = None) -> bool:
        if not isinstance(record, Mapping) or not isinstance(record.get("evidence_digest"), str):
            return False
        previous = record.get("previous_digest", "") if previous_digest is None else previous_digest
        if record.get("previous_digest", "") != previous:
            return False
        expected = evidence_digest(dict(record), previous)
        return expected == record["evidence_digest"]
