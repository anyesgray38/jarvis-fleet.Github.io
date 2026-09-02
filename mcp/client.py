"""Dependency-free MCP client with stdio and Streamable HTTP transports.

The client intentionally keeps the protocol surface small: discover a server,
list tools with pagination, and call a tool. AEGIS owns admission, policy,
verification, evidence, and progressive disclosure around this transport layer.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class McpError(RuntimeError):
    """Protocol, transport, or server-side MCP error."""


class Transport(Protocol):
    def request(self, message: dict[str, Any], *, timeout: float) -> dict[str, Any]: ...
    def close(self) -> None: ...


@dataclass
class StdioTransport:
    command: list[str]
    env: dict[str, str] | None = None
    cwd: str | None = None
    _process: subprocess.Popen[str] | None = field(default=None, init=False)
    _responses: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue, init=False)
    _counter: int = field(default=0, init=False)
    _reader: threading.Thread | None = field(default=None, init=False)

    def _ensure_process(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        if not self.command:
            raise McpError("stdio command cannot be empty")
        merged_env = os.environ.copy()
        if self.env:
            merged_env.update(self.env)
        self._process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=merged_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            shell=False,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                self._responses.put(payload)

    def request(self, message: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        self._ensure_process()
        process = self._process
        if process is None or process.stdin is None:
            raise McpError("stdio process is unavailable")
        self._counter += 1
        request_id = self._counter
        request = dict(message)
        request.setdefault("jsonrpc", "2.0")
        request["id"] = request_id
        process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                response = self._responses.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if response.get("id") == request_id:
                return response
        raise McpError(f"stdio MCP request timed out after {timeout:.1f}s")

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._reader = None


@dataclass
class StreamableHttpTransport:
    url: str
    headers: dict[str, str] = field(default_factory=dict)

    def request(self, message: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        method = str(message.get("method", ""))
        params = message.get("params", {}) or {}
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": method,
            **self.headers,
        }
        if method in {"tools/call", "resources/read", "prompts/get"}:
            name = params.get("name") or params.get("uri")
            if isinstance(name, str):
                request_headers["Mcp-Name"] = name
        request = Request(self.url, data=body, headers=request_headers, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise McpError(f"HTTP {exc.code}: {raw[:500]}") from exc
        except URLError as exc:
            raise McpError(f"MCP HTTP transport failed: {exc.reason}") from exc
        return _decode_http_payload(raw)

    def close(self) -> None:
        return None


def _decode_http_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        raise McpError("MCP HTTP response was empty")
    if text.startswith("data:") or "\ndata:" in text:
        data_lines = []
        for line in text.splitlines():
            if line.startswith("data:"):
                value = line[5:].strip()
                if value:
                    data_lines.append(value)
        if not data_lines:
            raise McpError("MCP SSE response did not contain JSON data")
        text = data_lines[-1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise McpError(f"MCP response was not JSON: {text[:300]}") from exc
    if not isinstance(payload, dict):
        raise McpError("MCP response must be a JSON object")
    return payload


def _check_response(response: dict[str, Any]) -> dict[str, Any]:
    if "error" in response:
        error = response.get("error")
        raise McpError(f"MCP server error: {error}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise McpError("MCP response has no result object")
    return result


class McpClient:
    """Small MCP client used by the AEGIS capability fabric."""

    def __init__(self, transport: Transport, *, client_name: str = "AEGIS", client_version: str = "1.0"):
        self.transport = transport
        self.client_name = client_name
        self.client_version = client_version
        self._initialized = False

    def _request(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 15.0) -> dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": dict(params or {}),
        }
        request["params"].setdefault(
            "_meta",
            {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientInfo": {"name": self.client_name, "version": self.client_version},
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        )
        return _check_response(self.transport.request(request, timeout=timeout))

    def discover(self, *, timeout: float = 15.0) -> dict[str, Any]:
        """Prefer current stateless discovery and fall back to lifecycle initialize."""
        try:
            result = self._request("server/discover", timeout=timeout)
            self._initialized = True
            return result
        except McpError:
            initialize = self._request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": self.client_name, "version": self.client_version},
                },
                timeout=timeout,
            )
            self._initialized = True
            return initialize

    def list_tools(self, *, timeout: float = 15.0, max_pages: int = 100) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(max_pages):
            params = {"cursor": cursor} if cursor else {}
            result = self._request("tools/list", params, timeout=timeout)
            page = result.get("tools", [])
            if not isinstance(page, list):
                raise McpError("tools/list returned a non-list tools field")
            tools.extend(x for x in page if isinstance(x, dict))
            cursor_value = result.get("nextCursor")
            if not cursor_value:
                return tools
            cursor = str(cursor_value)
        raise McpError(f"tools/list exceeded max_pages={max_pages}")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None, *, timeout: float = 30.0) -> dict[str, Any]:
        if not name:
            raise ValueError("tool name is required")
        return self._request("tools/call", {"name": name, "arguments": arguments or {}}, timeout=timeout)

    def close(self) -> None:
        self.transport.close()
