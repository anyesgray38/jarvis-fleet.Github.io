#!/usr/bin/env python3
"""Controlled MCP bridge from Hermes Agent into the AEGIS control plane.

Hermes is an operator-facing agent surface. This server exposes bounded reads,
planning, job inspection, and an explicitly safety-gated worker queue. It never
exposes credentials or unrestricted host shell access.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jarvis.capabilities import CapabilityRegistry
from routing import SkillRouter
from security.safety import SafetySettings


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "capabilities" / "registry.json"
ORCHESTRATOR_URL = os.environ.get("AEGIS_ORCHESTRATOR_URL", "http://127.0.0.1:8888").rstrip("/")
DESKTOP_RUNTIME_URL = os.environ.get("AEGIS_DESKTOP_RUNTIME_URL", "http://127.0.0.1:8894").rstrip("/")
MAX_READ_BYTES = 128_000
MAX_SEARCH_RESULTS = 100
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "secrets.json", "credentials.json"}
SENSITIVE_SUFFIXES = (".pem", ".key", ".crt", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db")
SKIP_DIRECTORIES = {".git", "__pycache__", "node_modules", ".next", "evidence"}


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "aegis_status",
            "description": "Read the current AEGIS orchestrator, worker, job, and safety state. Read-only.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "aegis_capabilities",
            "description": "List capabilities registered by AEGIS without executing any capability.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Optional substring filter."}},
                "additionalProperties": False,
            },
        },
        {
            "name": "aegis_plan",
            "description": "Route an objective to registered AEGIS capabilities and return a non-executing plan.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "capability": {"type": "string", "description": "Optional explicit registered capability."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["objective"],
                "additionalProperties": False,
            },
        },
        {
            "name": "aegis_inspect",
            "description": "Inspect the shape of a repository-local AEGIS file or directory.",
            "inputSchema": {
                "type": "object",
                "properties": {"target": {"type": "string", "description": "Repository-relative path; defaults to the repository root."}},
                "additionalProperties": False,
            },
        },
        {
            "name": "aegis_audit",
            "description": "Run a read-only Python syntax audit over a repository-local file or directory.",
            "inputSchema": {
                "type": "object",
                "properties": {"target": {"type": "string", "description": "Repository-relative Python path; defaults to the repository root."}},
                "additionalProperties": False,
            },
        },
        {
            "name": "aegis_read_file",
            "description": "Read a bounded UTF-8 text file inside the AEGIS repository. Credential-shaped files are blocked.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Repository-relative text file path."},
                    "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_READ_BYTES},
                },
                "required": ["target"],
                "additionalProperties": False,
            },
        },
        {
            "name": "aegis_search",
            "description": "Search repository-local text for a plain-text query without invoking a shell.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 200},
                    "target": {"type": "string", "description": "Optional repository-relative file or directory."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_RESULTS},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "aegis_job",
            "description": "Read the status and result of one AEGIS orchestrator job.",
            "inputSchema": {
                "type": "object",
                "properties": {"job_id": {"type": "integer", "minimum": 1}},
                "required": ["job_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "aegis_queue",
            "description": "Queue an authorized worker command. Requires confirm=true and the AEGIS raw_fleet safety control enabled.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "hostname": {"type": "string", "minLength": 1, "maxLength": 128},
                    "cmd": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "confirm": {"type": "boolean"},
                },
                "required": ["hostname", "cmd", "confirm"],
                "additionalProperties": False,
            },
        },
        {
            "name": "desktop_observe",
            "description": "Read the local Linux desktop state through the governed AEGIS desktop runtime. Observation is read-only and reports degraded backends honestly.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "desktop_screenshot",
            "description": "Capture the local desktop through AEGIS. The image is bounded and may be unavailable when the display backend cannot prove capture.",
            "inputSchema": {
                "type": "object",
                "properties": {"include_image": {"type": "boolean", "description": "Include bounded base64 PNG data in the result."}},
                "additionalProperties": False,
            },
        },
        {
            "name": "desktop_action",
            "description": "Perform one governed local desktop action. The runtime validates inputs, applies AEGIS safety controls, audits the action, and never accepts shell commands.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["move", "click", "double_click", "right_click", "scroll", "type", "hotkey", "drag", "wait"]},
                    "arguments": {"type": "object"},
                },
                "required": ["action", "arguments"],
                "additionalProperties": False,
            },
        },
        {
            "name": "desktop_verify",
            "description": "Verify one bounded desktop predicate after an action: backend_available, pointer_at, active_window_contains, or screenshot_changed.",
            "inputSchema": {"type": "object", "properties": {"condition": {"type": "object"}}, "required": ["condition"], "additionalProperties": False},
        },
        {
            "name": "desktop_stop",
            "description": "Immediately latch the local desktop runtime into stopped state. This emergency stop is always available and does not require a safety switch.",
            "inputSchema": {"type": "object", "properties": {"reason": {"type": "string", "maxLength": 200}}, "additionalProperties": False},
        },
        {
            "name": "desktop_resume",
            "description": "Resume a stopped local desktop runtime only with explicit confirm=true and the desktop_control safety switch enabled.",
            "inputSchema": {"type": "object", "properties": {"confirm": {"type": "boolean"}}, "required": ["confirm"], "additionalProperties": False},
        },
    ]


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, default=str)


def _text_result(value: Any, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _json(value)}], "isError": is_error}


def _http_json(path: str) -> dict[str, Any]:
    try:
        request = Request(f"{ORCHESTRATOR_URL}{path}", headers={"Accept": "application/json"})
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
        return payload if isinstance(payload, dict) else {"ok": False, "error": "invalid orchestrator response"}
    except (OSError, URLError, ValueError) as exc:
        return {"ok": False, "error": f"orchestrator unavailable: {exc}"}


def _http_post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{ORCHESTRATOR_URL}{path}",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=3) as response:
            value = json.loads(response.read(2_000_000).decode("utf-8"))
        return value if isinstance(value, dict) else {"ok": False, "error": "invalid orchestrator response"}
    except (OSError, URLError, ValueError) as exc:
        return {"ok": False, "error": f"orchestrator unavailable: {exc}"}


def _desktop_http(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{DESKTOP_RUNTIME_URL}{path}",
        data=body,
        headers={"Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {})},
        method=method,
    )
    try:
        with urlopen(request, timeout=5) as response:
            value = json.loads(response.read(5_000_000).decode("utf-8"))
        return value if isinstance(value, dict) else {"ok": False, "error": "invalid desktop runtime response"}
    except HTTPError as exc:
        if exc.code == 403:
            try:
                detail = json.loads(exc.read(1_000_000).decode("utf-8"))
            except (OSError, ValueError):
                detail = {"error": str(exc)}
            raise PermissionError(str(detail.get("error", "desktop action blocked"))) from exc
        return {"ok": False, "error": f"desktop runtime HTTP {exc.code}"}
    except Exception as exc:
        return {"ok": False, "error": f"desktop runtime unavailable: {exc}"}


def _status(_arguments: dict[str, Any]) -> dict[str, Any]:
    health = _http_json("/health")
    agents = _http_json("/agents")
    jobs = _http_json("/jobs")
    safety_path = Path(os.environ.get("JARVIS_SAFETY_CONFIG", str(ROOT / ".jarvis" / "safety.json")))
    try:
        safety = SafetySettings(safety_path).snapshot()
    except ValueError as exc:
        safety = {"error": str(exc)}
    return {
        "orchestrator": health,
        "agents": agents.get("agents", []),
        "jobs": jobs.get("jobs", []),
        "safety": safety,
        "desktop_runtime": _desktop_http("/health"),
        "execution": "not exposed by this bridge",
    }


def _capabilities(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query", "")).strip().casefold()
    rows = []
    for capability in CapabilityRegistry(REGISTRY_PATH).list():
        if query and query not in json.dumps(capability, sort_keys=True).casefold():
            continue
        rows.append({
            key: capability.get(key)
            for key in ("id", "provider", "kind", "tags", "execution", "verification", "action")
            if key in capability
        })
    return {"count": len(rows), "capabilities": rows}


def _plan(arguments: dict[str, Any]) -> dict[str, Any]:
    objective = str(arguments.get("objective", "")).strip()
    if not objective or len(objective) > 2000:
        raise ValueError("objective must be between 1 and 2000 characters")
    capability_id = str(arguments.get("capability", "")).strip()
    if capability_id:
        capability = CapabilityRegistry(REGISTRY_PATH).get(capability_id)
        return {
            "objective": objective,
            "selected": {"capability": capability_id, "provider": capability.get("provider"), "verification": capability.get("verification", [])},
            "execution": "not performed; submit through an explicit AEGIS approval path",
        }
    limit = max(1, min(10, int(arguments.get("limit", 5))))
    routes = SkillRouter(REGISTRY_PATH).route(objective, limit=limit)
    return {
        "objective": objective,
        "routes": [
            {
                "capability": route.capability_id,
                "provider": route.provider,
                "score": route.score,
                "matched_terms": list(route.matched_terms),
                "verification": list(route.verification),
                "skill": route.skill,
                "requires_authorization": route.requires_authorization,
            }
            for route in routes
        ],
        "execution": "not performed; submit through an explicit AEGIS approval path",
    }


def _safe_target(raw: Any) -> Path:
    value = str(raw or ".").strip()
    if not value:
        value = "."
    target = Path(value).expanduser().resolve()
    if target != ROOT and ROOT not in target.parents:
        raise PermissionError("target must remain inside the AEGIS repository")
    if not target.exists():
        raise FileNotFoundError(f"target not found: {value}")
    return target


def _inspect(arguments: dict[str, Any]) -> dict[str, Any]:
    target = _safe_target(arguments.get("target"))
    if target.is_file():
        return {"path": str(target.relative_to(ROOT)), "type": "file", "bytes": target.stat().st_size}
    entries = sorted(target.iterdir(), key=lambda path: (not path.is_dir(), path.name.casefold()))
    return {
        "path": str(target.relative_to(ROOT)) or ".",
        "type": "directory",
        "entries": [{"name": item.name, "type": "directory" if item.is_dir() else "file"} for item in entries[:200]],
        "truncated": len(entries) > 200,
    }


def _audit(arguments: dict[str, Any]) -> dict[str, Any]:
    target = _safe_target(arguments.get("target"))
    files = [target] if target.is_file() else sorted(target.rglob("*.py"))
    failures: list[dict[str, str]] = []
    for path in files[:500]:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            failures.append({"path": str(path.relative_to(ROOT)), "error": str(exc)})
    return {
        "target": str(target.relative_to(ROOT)) or ".",
        "mode": "read_only_syntax_audit",
        "files_checked": min(len(files), 500),
        "truncated": len(files) > 500,
        "syntax_ok": not failures and len(files) <= 500,
        "failures": failures,
    }


def _sensitive_path(path: Path) -> bool:
    name = path.name.casefold()
    return name in SENSITIVE_NAMES or name.endswith(SENSITIVE_SUFFIXES) or any(
        marker in name for marker in ("secret", "credential", "private_key")
    )


def _read_file(arguments: dict[str, Any]) -> dict[str, Any]:
    target = _safe_target(arguments.get("target"))
    if not target.is_file():
        raise IsADirectoryError("target must be a file")
    if _sensitive_path(target):
        raise PermissionError("credential-shaped files are not readable through Hermes")
    max_bytes = max(1, min(MAX_READ_BYTES, int(arguments.get("max_bytes", MAX_READ_BYTES))))
    raw = target.read_bytes()
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("target is not UTF-8 text") from exc
    return {
        "path": str(target.relative_to(ROOT)),
        "bytes_returned": len(raw),
        "truncated": target.stat().st_size > len(raw),
        "content": content,
    }


def _search(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query", ""))
    if not query or len(query) > 200:
        raise ValueError("query must be between 1 and 200 characters")
    target = _safe_target(arguments.get("target"))
    limit = max(1, min(MAX_SEARCH_RESULTS, int(arguments.get("limit", 50))))
    files = [target] if target.is_file() else sorted(
        path for path in target.rglob("*")
        if path.is_file() and not any(part in SKIP_DIRECTORIES for part in path.relative_to(ROOT).parts)
    )
    results: list[dict[str, Any]] = []
    needle = query.casefold()
    for path in files:
        if len(results) >= limit or _sensitive_path(path) or path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if needle in line.casefold():
                results.append({"path": str(path.relative_to(ROOT)), "line": line_number, "text": line[:500]})
                if len(results) >= limit:
                    break
    return {"query": query, "count": len(results), "results": results, "truncated": len(results) >= limit}


def _job(arguments: dict[str, Any]) -> dict[str, Any]:
    job_id = int(arguments.get("job_id", 0))
    if job_id < 1:
        raise ValueError("job_id must be positive")
    return _http_json(f"/jobs/{job_id}")


def _queue(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("confirm") is not True:
        raise PermissionError("queueing requires confirm=true")
    safety_path = Path(os.environ.get("JARVIS_SAFETY_CONFIG", str(ROOT / ".jarvis" / "safety.json")))
    settings = SafetySettings(safety_path)
    if not settings.enabled("raw_fleet"):
        raise PermissionError("blocked by AEGIS safety control 'raw_fleet'")
    hostname = str(arguments.get("hostname", "")).strip()
    cmd = str(arguments.get("cmd", "")).strip()
    if not hostname or len(hostname) > 128 or not cmd or len(cmd) > 2000:
        raise ValueError("hostname and cmd are required within their limits")
    return _http_post_json("/queue", {"hostname": hostname, "cmd": cmd})


def _desktop_observe(_arguments: dict[str, Any]) -> dict[str, Any]:
    return _desktop_http("/observe")


def _desktop_screenshot(arguments: dict[str, Any]) -> dict[str, Any]:
    include_image = bool(arguments.get("include_image", False))
    return _desktop_http("/screenshot" + ("?include_image=true" if include_image else ""))


def _desktop_action(arguments: dict[str, Any]) -> dict[str, Any]:
    action = str(arguments.get("action", "")).strip()
    value = arguments.get("arguments")
    if not action or not isinstance(value, dict):
        raise ValueError("action and arguments object are required")
    return _desktop_http("/action", method="POST", payload={"action": action, "arguments": value})


def _desktop_verify(arguments: dict[str, Any]) -> dict[str, Any]:
    condition = arguments.get("condition")
    if not isinstance(condition, dict):
        raise ValueError("condition must be an object")
    return _desktop_http("/verify", method="POST", payload={"condition": condition})


def _desktop_stop(arguments: dict[str, Any]) -> dict[str, Any]:
    reason = str(arguments.get("reason", "operator"))[:200]
    return _desktop_http("/stop", method="POST", payload={"reason": reason})


def _desktop_resume(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("confirm") is not True:
        raise PermissionError("desktop resume requires confirm=true")
    return _desktop_http("/resume", method="POST", payload={"confirm": True})


def _call(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    handlers = {
        "aegis_status": _status,
        "aegis_capabilities": _capabilities,
        "aegis_plan": _plan,
        "aegis_inspect": _inspect,
        "aegis_audit": _audit,
        "aegis_read_file": _read_file,
        "aegis_search": _search,
        "aegis_job": _job,
        "aegis_queue": _queue,
        "desktop_observe": _desktop_observe,
        "desktop_screenshot": _desktop_screenshot,
        "desktop_action": _desktop_action,
        "desktop_verify": _desktop_verify,
        "desktop_stop": _desktop_stop,
        "desktop_resume": _desktop_resume,
    }
    try:
        handler = handlers[name]
    except KeyError as exc:
        raise ValueError(f"unknown AEGIS tool: {name}") from exc
    return handler(arguments)


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return None
    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    if method in {"initialize", "server/discover"}:
        requested = params.get("protocolVersion", "2025-11-25")
        return _response(request_id, {
            "protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "aegis", "version": "1.0.0"},
        })
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": _tools()})
    if method == "tools/call":
        name = params.get("name")
        try:
            return _response(request_id, _text_result(_call(str(name), params.get("arguments", {}))))
        except Exception as exc:
            return _response(request_id, _text_result({"error": str(exc)}, is_error=True))
    return _error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            response = handle(request)
        except (json.JSONDecodeError, ValueError) as exc:
            response = _error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
