"""AEGIS Model Context Protocol capability fabric."""

from .client import McpClient, McpError, StdioTransport, StreamableHttpTransport
from .fabric import McpCapabilityFabric
from .catalog import MCPServerRecord, parse_catalog
from .admission import AdmissionController, AdmissionDecision

__all__ = [
    "McpClient",
    "McpError",
    "StdioTransport",
    "StreamableHttpTransport",
    "McpCapabilityFabric",
    "MCPServerRecord",
    "parse_catalog",
    "AdmissionController",
    "AdmissionDecision",
]
