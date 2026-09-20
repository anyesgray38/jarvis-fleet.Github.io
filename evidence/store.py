"""Append-only JSONL evidence store for Jarvis task executions."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.verification import evidence_digest


class EvidenceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        record = dict(event)
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        previous = ""
        if self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if lines:
                try:
                    previous = json.loads(lines[-1]).get("evidence_digest", "")
                except json.JSONDecodeError:
                    previous = ""
        record["evidence_digest"] = evidence_digest(record, previous)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        return record
