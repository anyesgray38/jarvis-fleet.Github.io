"""Deterministic, auditable routing for AEGIS capabilities and skills.

The router narrows the search space. It never executes tools and never grants
permissions; authorization remains the responsibility of the execution policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_.-]*")

@dataclass(frozen=True)
class RouteDecision:
    capability_id: str
    provider: str
    score: int
    matched_terms: tuple[str, ...]
    verification: tuple[str, ...]
    skill: str | None = None
    requires_authorization: bool = False

class SkillRouter:
    """Resolve an objective to registered capabilities without side effects."""
    def __init__(self, registry_path: str | Path, skills_root: str | Path | None = None):
        self.registry_path = Path(registry_path)
        self.skills_root = Path(skills_root) if skills_root else self.registry_path.parent.parent / "skills"
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.capabilities = tuple(payload.get("capabilities", ()))

    @staticmethod
    def _terms(text: str) -> set[str]:
        return set(_TOKEN.findall(text.lower()))

    def available_skills(self) -> tuple[str, ...]:
        if not self.skills_root.is_dir(): return ()
        return tuple(sorted(p.name for p in self.skills_root.iterdir() if p.is_dir()))

    def route(self, objective: str, *, limit: int = 5) -> list[RouteDecision]:
        if not objective.strip() or limit < 1: return []
        query, skills, decisions = self._terms(objective), set(self.available_skills()), []
        for cap in self.capabilities:
            cid = str(cap.get("id", ""))
            tags = {str(tag).lower() for tag in cap.get("tags", [])}
            identity = self._terms(cid.replace(".", " "))
            matched = query & (tags | identity)
            if not matched: continue
            score = 3 * len(query & tags) + len(query & identity)
            decisions.append(RouteDecision(
                capability_id=cid, provider=str(cap.get("provider", "")), score=score,
                matched_terms=tuple(sorted(matched)),
                verification=tuple(str(v) for v in cap.get("verification", [])),
                skill=self._skill_for(tags | identity, skills),
                requires_authorization=(str(cap.get("kind", "")).lower() == "security" or "security" in tags),
            ))
        decisions.sort(key=lambda item: (-item.score, item.capability_id))
        return decisions[:limit]

    @staticmethod
    def _skill_for(terms: set[str], skills: set[str]) -> str | None:
        aliases = (
            ("builder", {"builder", "app", "scaffold"}),
            ("website-operation", {"website", "browser", "web"}),
            ("github-research", {"github", "repository", "research"}),
            ("coding", {"coding", "software", "frontend"}),
            ("testing", {"testing", "tests", "verification"}),
            ("debugging", {"debugging", "repair"}),
            ("computer-use", {"computer", "terminal"}),
        )
        for skill, triggers in aliases:
            if skill in skills and terms & triggers: return skill
        return next((skill for skill in sorted(skills) if skill in terms), None)
