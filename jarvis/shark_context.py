"""Lazy-loading context profiles for the Shark AI runtime."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "shark_profiles" / "manifest.json"
CORE = ROOT / "config" / "shark_ai_core.md"


def load_context(purpose: str = "general") -> str:
    """Return only the core prompt plus profiles required for the task purpose."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    parts = [CORE.read_text(encoding="utf-8")]
    profile_names = manifest.get("routing", {}).get(purpose, [])
    profiles = manifest.get("profiles", {})
    for name in profile_names:
        path = profiles.get(name)
        if not isinstance(path, str):
            continue
        parts.append((ROOT / path).read_text(encoding="utf-8"))
    return "\n\n--- ON-DEMAND PROFILE ---\n\n".join(parts)


def apply_context(messages: list[dict[str, str]], purpose: str = "general") -> list[dict[str, str]]:
    """Return a new message list with lazy Shark context as one system message."""
    context = load_context(purpose)
    return [{"role": "system", "content": context}, *messages]
