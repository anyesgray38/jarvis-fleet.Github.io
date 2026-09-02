import unittest

from mcp.admission import AdmissionController
from mcp.catalog import parse_catalog
from mcp.fabric import McpCapabilityFabric, RegisteredServer
from mcp.result_store import MCPResultStore


class FakeClient:
    def __init__(self):
        self.called = []

    def discover(self, *, timeout=15.0):
        self.called.append(("discover", timeout))
        return {"capabilities": {"tools": {}}}

    def list_tools(self, *, timeout=15.0):
        self.called.append(("list_tools", timeout))
        return [
            {
                "name": "search",
                "description": "Search public research sources",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
            }
        ]

    def call_tool(self, name, arguments=None, *, timeout=30.0):
        self.called.append(("call_tool", name, arguments, timeout))
        return {"content": [{"type": "text", "text": "ok"}]}

    def close(self):
        self.called.append(("close",))


class MCPFabricTests(unittest.TestCase):
    def test_catalog_parser_normalizes_category(self):
        markdown = """### 🔬 <a name=\"research\"></a>Research\n- [Demo](https://example.com/mcp) 🐍 ☁️ - Evidence search server."""
        records = parse_catalog(markdown)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].category, "Research")
        self.assertIn("research", records[0].tags)
        self.assertEqual(records[0].language, "python")
        self.assertEqual(records[0].scope, ("cloud",))

    def test_admission_rejects_command_surface(self):
        controller = AdmissionController(max_risk_score=5)
        decision = controller.inspect(
            {"id": "unsafe"},
            [{"name": "exec", "description": "Execute shell commands", "inputSchema": {"type": "object"}}],
        )
        self.assertFalse(decision.approved)
        self.assertIn("command_execution", decision.permissions)

    def test_admitted_tool_can_be_searched_and_invoked(self):
        fabric = McpCapabilityFabric()
        fake = FakeClient()
        fabric._servers["demo"] = RegisteredServer(spec={"id": "demo"}, client=fake)
        decision = fabric.discover("demo")
        self.assertTrue(decision.approved)
        matches = fabric.list_capabilities(query="search")
        self.assertEqual(matches[0]["tool"], "search")
        result = fabric.invoke("demo", "search", {"query": "MCP"})
        self.assertEqual(result["content"][0]["text"], "ok")

    def test_large_result_gets_handle(self):
        store = MCPResultStore(max_inline_chars=256)
        envelope = store.envelope({"payload": "x" * 1000})
        self.assertTrue(envelope.truncated)
        self.assertIsNotNone(envelope.handle)
        recovered = store.read_more(envelope.handle)
        self.assertIn("payload", recovered)


if __name__ == "__main__":
    unittest.main()
