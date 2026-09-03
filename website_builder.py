"""Translate a website objective into a governed AEGIS action request."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WebsiteObjective:
    """Validated website-generation objective."""

    name: str
    title: str
    description: str
    accent: str = "#7dd3fc"
    overwrite: bool = False

    def to_action(self, task_id: str, workspace: str) -> dict[str, Any]:
        """Return the action payload consumed by the Action Fabric."""
        return {
            "task_id": task_id,
            "capability": "core.website_generation",
            "action": "website.create",
            "input": {
                "name": self.name,
                "title": self.title,
                "description": self.description,
                "accent": self.accent,
                "overwrite": self.overwrite,
            },
            "workspace": workspace,
            "verification": {
                "required": True,
                "checks": ["filesystem_integrity", "build_validation", "browser_check", "self_audit"],
            },
        }


def build_website_action(
    *,
    task_id: str,
    workspace: str,
    name: str,
    title: str,
    description: str,
    accent: str = "#7dd3fc",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a planner-ready website action without executing it."""
    objective = WebsiteObjective(name, title, description, accent, overwrite)
    return objective.to_action(task_id, workspace)
