"""Fail-closed validation for AEGIS Fleet configuration."""
from __future__ import annotations

import re
from typing import Any


class FleetConfigError(ValueError):
    """Raised when Fleet configuration is unsafe or structurally invalid."""


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TRUST_LEVELS = {"untrusted", "trusted", "verified"}
_STATUSES = {"unknown", "connected", "disconnected"}


def _require(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise FleetConfigError(f"missing required field: {context}.{key}")
    return mapping[key]


def _env_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ENV_NAME.fullmatch(value):
        raise FleetConfigError(f"{field} must be a valid environment-variable name")
    return value


def validate_fleet_config(data: Any) -> dict[str, Any]:
    """Validate a Fleet config without requiring live credentials or network state."""
    if not isinstance(data, dict):
        raise FleetConfigError("Fleet config must be a JSON object")

    network = _require(data, "network", "config")
    enrollment = _require(data, "enrollment", "config")
    signing = _require(data, "signing", "config")
    nodes = _require(data, "nodes", "config")

    if not isinstance(network, dict) or network.get("provider") != "tailscale":
        raise FleetConfigError("network.provider must be 'tailscale'")
    if network.get("allow_public_bind", False) is not False:
        raise FleetConfigError("public binds must remain disabled")
    if not isinstance(network.get("approved_exit_nodes", []), list):
        raise FleetConfigError("network.approved_exit_nodes must be a list")

    if not isinstance(enrollment, dict):
        raise FleetConfigError("config.enrollment must be an object")
    allowlist = _require(enrollment, "network_allowlist", "enrollment")
    if not isinstance(allowlist, list) or "tailscale" not in allowlist:
        raise FleetConfigError("enrollment.network_allowlist must include tailscale")
    _env_name(_require(enrollment, "bootstrap_token_env", "enrollment"), "enrollment.bootstrap_token_env")
    if enrollment.get("new_nodes_start_untrusted") is not True:
        raise FleetConfigError("new nodes must start untrusted")
    if enrollment.get("require_attestation_before_execution") is not True:
        raise FleetConfigError("attestation must be required before execution")

    if not isinstance(signing, dict):
        raise FleetConfigError("config.signing must be an object")
    if signing.get("algorithm") != "hmac-sha256":
        raise FleetConfigError("signing.algorithm must be hmac-sha256")
    _env_name(_require(signing, "secret_env", "signing"), "signing.secret_env")
    age = _require(signing, "max_request_age_seconds", "signing")
    if not isinstance(age, int) or isinstance(age, bool) or not 1 <= age <= 300:
        raise FleetConfigError("signing.max_request_age_seconds must be an integer from 1 to 300")

    if not isinstance(nodes, list):
        raise FleetConfigError("config.nodes must be a list")
    seen: set[str] = set()
    for index, node in enumerate(nodes):
        context = f"nodes[{index}]"
        if not isinstance(node, dict):
            raise FleetConfigError(f"{context} must be an object")
        node_id = _require(node, "node_id", context)
        if not isinstance(node_id, str) or not node_id or node_id in seen:
            raise FleetConfigError(f"{context}.node_id must be unique and non-empty")
        seen.add(node_id)
        if node.get("network") != "tailscale":
            raise FleetConfigError(f"{context}.network must be tailscale")
        if node.get("trust", "untrusted") not in _TRUST_LEVELS:
            raise FleetConfigError(f"{context}.trust is invalid")
        if node.get("status", "unknown") not in _STATUSES:
            raise FleetConfigError(f"{context}.status is invalid")
        for field in ("capabilities", "modalities", "labels"):
            if not isinstance(node.get(field, []), list):
                raise FleetConfigError(f"{context}.{field} must be a list")

    return data
