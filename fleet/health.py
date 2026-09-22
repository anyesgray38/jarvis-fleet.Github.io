"""Pure health scoring primitives for Fleet scheduling and admission."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import json
import subprocess
import time
from typing import Any, Callable

from .node import FleetNode


class TailscaleHealthError(RuntimeError):
    """Raised when Tailscale health data cannot be read or decoded."""

@dataclass(frozen=True)
class HealthSnapshot:
    reachable: bool
    latency_ms: float | None = None
    load: float | None = None
    last_seen_age_s: float | None = None

    @property
    def healthy(self) -> bool:
        if not self.reachable:
            return False
        if self.last_seen_age_s is not None and self.last_seen_age_s > 120:
            return False
        if self.load is not None and not 0 <= self.load <= 1:
            return False
        return True

    def score(self) -> float:
        if not self.healthy:
            return 0.0
        score = 50.0
        if self.latency_ms is not None:
            score += max(0.0, 25.0 - min(25.0, self.latency_ms / 10.0))
        if self.load is not None:
            score += 25.0 * (1.0 - self.load)
        return score


def _timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class TailscaleHealthProvider:
    """Read-only health provider backed by ``tailscale status --json``.

    The command runner is injectable so health evaluation stays deterministic in
    tests and does not require a live Tailscale daemon in the control plane.
    """

    def __init__(self, *, command: tuple[str, ...] = ("tailscale", "status", "--json"),
                 runner: Callable[..., Any] | None = None, max_age_seconds: float = 120.0):
        self.command = command
        self.runner = runner or subprocess.run
        self.max_age_seconds = max_age_seconds

    def _status(self) -> dict[str, Any]:
        result = self.runner(list(self.command), capture_output=True, text=True, timeout=10, check=False)
        if getattr(result, "returncode", 1) != 0:
            raise TailscaleHealthError(getattr(result, "stderr", "").strip() or "tailscale status failed")
        try:
            payload = json.loads(getattr(result, "stdout", ""))
        except json.JSONDecodeError as exc:
            raise TailscaleHealthError("tailscale status returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TailscaleHealthError("tailscale status must return an object")
        return payload

    @staticmethod
    def _matches(node: FleetNode, candidate: dict[str, Any]) -> bool:
        metadata = node.metadata
        identifiers = {
            node.node_id,
            node.address,
            metadata.get("tailscale_id"),
            metadata.get("hostname"),
            metadata.get("dns_name"),
        }
        candidate_values = {
            candidate.get("ID"), candidate.get("HostName"), candidate.get("DNSName"),
            candidate.get("Name"), *(candidate.get("TailscaleIPs") or []),
        }
        return bool({item for item in identifiers if item} & {item for item in candidate_values if item})

    def snapshot(self, node: FleetNode, *, now: float | None = None) -> HealthSnapshot:
        if node.network != "tailscale":
            return HealthSnapshot(reachable=False)
        payload = self._status()
        peers = payload.get("Peer", {})
        candidates = list(peers.values()) if isinstance(peers, dict) else []
        own = payload.get("Self")
        if isinstance(own, dict):
            candidates.append(own)
        candidate = next((item for item in candidates if isinstance(item, dict) and self._matches(node, item)), None)
        if candidate is None:
            return HealthSnapshot(reachable=False)
        current = time.time() if now is None else now
        last_seen = _timestamp(candidate.get("LastSeen") or candidate.get("LastHandshake"))
        age = max(0.0, current - last_seen) if last_seen is not None else None
        online = candidate.get("Online")
        reachable = online is True or (online is None and age is not None and age <= self.max_age_seconds)
        latency = candidate.get("LatencyMS", candidate.get("LatencyMs"))
        if not isinstance(latency, (int, float)) or isinstance(latency, bool):
            latency = None
        return HealthSnapshot(reachable=reachable, latency_ms=float(latency) if latency is not None else None,
                              last_seen_age_s=age)
