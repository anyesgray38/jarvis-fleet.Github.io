"""Governed execution fabric for arbitrary MCP servers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .admission import AdmissionController, AdmissionDecision
from .client import McpClient, StdioTransport, StreamableHttpTransport
from .result_store import MCPResultStore, ResultEnvelope


@dataclass
class RegisteredServer:
    spec: dict[str, Any]
    client: McpClient
    tools: list[dict[str, Any]] = field(default_factory=list)
    admission: AdmissionDecision | None = None


class McpCapabilityFabric:
    """One AEGIS-owned control plane for local and remote MCP servers.

    Servers are registered as data, discovered lazily, admitted before exposure,
    and invoked only through a single governed path. This means hundreds or
    thousands of catalog entries do not become thousands of bespoke adapters.
    """

    def __init__(
        self,
        *,
        admission: AdmissionController | None = None,
        policy: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
        evidence: Any | None = None,
        result_store: MCPResultStore | None = None,
    ) -> None:
        self.admission = admission or AdmissionController()
        self.policy = policy
        self.evidence = evidence
        self.result_store = result_store or MCPResultStore()
        self._servers: dict[str, RegisteredServer] = {}

    def register(self, spec: dict[str, Any]) -> None:
        server_id = str(spec.get("id") or spec.get("name") or "")
        if not server_id:
            raise ValueError("MCP server id is required")
        transport = str(spec.get("transport", "streamable_http"))
        if transport == "stdio":
            command = spec.get("command")
            args = spec.get("args", [])
            if not isinstance(command, str) or not command:
                raise ValueError("stdio MCP server requires command")
            if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
                raise ValueError("stdio args must be a list of strings")
            client = McpClient(StdioTransport([command, *args], env=spec.get("env"), cwd=spec.get("cwd")))
        elif transport == "streamable_http":
            url = spec.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError("streamable_http MCP server requires an http(s) url")
            headers = spec.get("headers", {})
            if not isinstance(headers, dict):
                raise ValueError("MCP headers must be an object")
            client = McpClient(StreamableHttpTransport(url, headers={str(k): str(v) for k, v in headers.items()}))
        else:
            raise ValueError(f"unsupported MCP transport: {transport}")
        self._servers[server_id] = RegisteredServer(spec=dict(spec), client=client)
        self._record("mcp.registered", server_id, {"transport": transport})

    def discover(self, server_id: str, *, scanner: str | None = None, timeout: float = 15.0) -> AdmissionDecision:
        server = self._get(server_id)
        discovery = server.client.discover(timeout=timeout)
        tools = server.client.list_tools(timeout=timeout)
        decision = self.admission.inspect({**server.spec, "discovery": discovery}, tools, scanner=scanner)
        server.tools = tools
        server.admission = decision
        self._record("mcp.admitted", server_id, decision.to_dict())
        if not decision.approved:
            self._record("mcp.rejected", server_id, {"reasons": decision.reasons, "risk_score": decision.risk_score})
        return decision

    def list_capabilities(self, *, query: str | None = None, approved_only: bool = True) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tokens = _tokens(query or "")
        for server_id, server in self._servers.items():
            if approved_only and not (server.admission and server.admission.approved):
                continue
            for tool in server.tools:
                score = _relevance(tokens, server_id, tool)
                if query and score <= 0:
                    continue
                rows.append({
                    "server": server_id,
                    "tool": str(tool.get("name", "")),
                    "title": tool.get("title"),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("inputSchema", {}),
                    "permissions": list(server.admission.permissions) if server.admission else [],
                    "relevance": score,
                })
        return sorted(rows, key=lambda x: (-x["relevance"], x["server"], x["tool"]))

    def invoke(self, server_id: str, tool: str, arguments: dict[str, Any] | None = None, *, timeout: float = 30.0) -> dict[str, Any]:
        server = self._get(server_id)
        if not server.admission or not server.admission.approved:
            raise PermissionError(f"MCP server {server_id!r} is not admitted")
        tool_spec = next((x for x in server.tools if x.get("name") == tool), None)
        if tool_spec is None:
            raise LookupError(f"MCP tool {server_id}/{tool} was not discovered")
        request = {"server": server_id, "tool": tool, "arguments": arguments or {}}
        if self.policy:
            self.policy(tool_spec, request)
        self._record("mcp.tool.requested", server_id, {"tool": tool})
        result = server.client.call_tool(tool, arguments or {}, timeout=timeout)
        self._record("mcp.tool.completed", server_id, {"tool": tool, "result_type": type(result).__name__})
        return result

    def invoke_bounded(self, server_id: str, tool: str, arguments: dict[str, Any] | None = None, *, timeout: float = 30.0) -> ResultEnvelope:
        """Invoke a tool but keep oversized output behind a retrievable handle."""
        result = self.invoke(server_id, tool, arguments, timeout=timeout)
        envelope = self.result_store.envelope(result)
        self._record(
            "mcp.result.bounded",
            server_id,
            {"tool": tool, "sha256": envelope.sha256, "serialized_bytes": envelope.serialized_bytes, "truncated": envelope.truncated},
        )
        return envelope

    def read_more(self, handle: str, *, offset: int = 0, length: int | None = None) -> str:
        return self.result_store.read_more(handle, offset=offset, length=length)

    def close(self) -> None:
        for server in self._servers.values():
            server.client.close()

    def _get(self, server_id: str) -> RegisteredServer:
        try:
            return self._servers[server_id]
        except KeyError as exc:
            raise LookupError(f"unknown MCP server: {server_id}") from exc

    def _record(self, event: str, server_id: str, data: dict[str, Any]) -> None:
        if self.evidence is not None:
            self.evidence.append({"event": event, "server_id": server_id, **data})


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1}


def _relevance(tokens: set[str], server_id: str, tool: dict[str, Any]) -> float:
    if not tokens:
        return 1.0
    name_tokens = _tokens(str(tool.get("name", "")))
    description_tokens = _tokens(str(tool.get("description", "")))
    server_tokens = _tokens(server_id)
    score = 0.0
    score += 3.0 * len(tokens & name_tokens)
    score += 2.0 * len(tokens & server_tokens)
    score += 1.0 * len(tokens & description_tokens)
    return score
