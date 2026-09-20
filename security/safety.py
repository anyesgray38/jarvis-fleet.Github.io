"""Runtime safety controls for Jarvis.

Safety switches are explicit, persisted, and fail closed. They are intentionally
separate from model/provider settings so changing a provider cannot silently
change what Jarvis is allowed to do.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULTS = {
    "shell_execution": False,
    "external_network": False,
    "destructive_actions": False,
    "production_deploy": False,
    "raw_fleet": False,
    "autonomous_execution": False,
    "secret_access": False,
    "git_write": False,
}


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    control: str | None
    reason: str


class SafetySettings:
    """Persistent feature flags for practices that increase execution risk."""

    def __init__(self, path: str | Path = ".jarvis/safety.json") -> None:
        self.path = Path(path)
        self._lock = RLock()
        self._data = dict(DEFAULTS)
        self._load()

    @property
    def controls(self) -> tuple[str, ...]:
        return tuple(DEFAULTS)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("safety settings must be a JSON object")
            for key in DEFAULTS:
                if key in raw:
                    self._data[key] = bool(raw[key])
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid safety settings: {exc}") from exc

    def enabled(self, control: str) -> bool:
        if control not in DEFAULTS:
            raise KeyError(f"unknown safety control: {control}")
        with self._lock:
            return self._data[control]

    def set(self, control: str, enabled: bool, *, persist: bool = True) -> None:
        if control not in DEFAULTS:
            raise KeyError(f"unknown safety control: {control}")
        with self._lock:
            self._data[control] = bool(enabled)
            if persist:
                self._save()

    def snapshot(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._data)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class SafetyController:
    """Central gate used by execution code before a risky operation."""

    def __init__(self, settings: SafetySettings | None = None) -> None:
        self.settings = settings or SafetySettings()

    def check(self, control: str | None) -> SafetyDecision:
        if not control:
            return SafetyDecision(True, None, "no elevated safety control required")
        if self.settings.enabled(control):
            return SafetyDecision(True, control, f"{control} is enabled")
        return SafetyDecision(False, control, f"{control} is disabled")

    def require(self, control: str) -> None:
        decision = self.check(control)
        if not decision.allowed:
            raise PermissionError(
                f"blocked by safety control '{control}'; "
                f"enable it explicitly before this operation"
            )


CAPABILITY_CONTROLS = {
    "shell.execute": "shell_execution",
    "fleet.shell": "shell_execution",
    "fleet.broadcast": "raw_fleet",
    "fleet.parallel": "raw_fleet",
    "fleet.queue": "raw_fleet",
    "deploy.production": "production_deploy",
    "git.write": "git_write",
    "secrets.read": "secret_access",
    "network.request": "external_network",
    "network.fetch": "external_network",
    "system.delete": "destructive_actions",
}


def control_for_capability(capability: str) -> str | None:
    return CAPABILITY_CONTROLS.get(capability)


def capability_allowed(capability: str, settings: SafetySettings | None = None) -> SafetyDecision:
    return SafetyController(settings).check(control_for_capability(capability))
