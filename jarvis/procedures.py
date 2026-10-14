"""Versioned procedures are data, never executable code or authorization."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


ACTIVITIES = {"inspect", "research", "change", "operate", "unknown"}


@dataclass(frozen=True)
class Procedure:
    id: str
    version: int
    activity: str
    capabilities: tuple[str, ...]
    instructions: tuple[str, ...]
    status: str = "provisional"
    test_refs: tuple[str, ...] = ()

    def validate(self):
        if not self.id.strip() or type(self.version) is not int or self.version < 1:
            raise ValueError("procedure requires an id and positive integer version")
        if self.activity not in ACTIVITIES or self.status not in {"provisional", "reviewed"}:
            raise ValueError("invalid procedure activity or status")
        if not self.capabilities or not self.instructions:
            raise ValueError("procedure requires capabilities and instructions")
        if not all(isinstance(x, str) and x.strip() for x in (*self.capabilities, *self.instructions, *self.test_refs)):
            raise ValueError("procedure fields must be nonempty strings")
        if self.status == "reviewed" and not self.test_refs:
            raise ValueError("reviewed procedures require regression test references")

    def to_dict(self):
        return asdict(self)


class SOPRegistry:
    def __init__(self, procedures=()):
        self._versions = {}
        for procedure in procedures:
            self.add(procedure)

    @classmethod
    def from_file(cls, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("version") != 1:
            raise ValueError("unsupported SOP registry version")
        return cls(Procedure(
            id=p["id"], version=p["version"], activity=p["activity"],
            capabilities=tuple(p["capabilities"]), instructions=tuple(p["instructions"]),
            status=p.get("status", "provisional"), test_refs=tuple(p.get("test_refs", ())),
        ) for p in data["procedures"])

    def add(self, procedure: Procedure):
        """Trusted configuration API; task input cannot mutate this registry."""
        procedure.validate()
        key = (procedure.id, procedure.version)
        if key in self._versions:
            raise ValueError("procedure version already exists; create a new version")
        self._versions[key] = procedure

    def select(self, activity: str, capability: str) -> tuple[Procedure, str]:
        matches = [p for p in self._versions.values() if p.activity == activity
                   and capability in p.capabilities and p.status == "reviewed"]
        if matches:
            selected = sorted(matches, key=lambda p: (-p.version, p.id))[0]
            return selected, "Reviewed SOP matches the activity and registered capability."
        draft = Procedure(
            id=f"provisional:{activity}:{capability}", version=1, activity=activity,
            capabilities=(capability,), instructions=(
                "Confirm objective, constraints, environment and measurable success criteria.",
                "Review this provisional procedure and obtain required authorization.",
                "Invoke only the selected registered capability within resource limits.",
                "Evaluate captured evidence; escalate failures and retain only verified lessons.",
            ),
        )
        return draft, "No reviewed SOP matches; this provisional procedure requires review before execution."
