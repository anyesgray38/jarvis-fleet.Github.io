import json
import sys
import unittest
from pathlib import Path

from mcp.client import McpClient, StdioTransport


ROOT = Path(__file__).resolve().parents[1]


class HermesMcpServerTests(unittest.TestCase):
    def setUp(self):
        self.transport = StdioTransport([sys.executable, str(ROOT / "hermes_mcp_server.py")], cwd=str(ROOT))
        self.client = McpClient(self.transport, client_name="test-hermes")

    def tearDown(self):
        self.client.close()

    def test_discovers_read_only_aegis_tools(self):
        result = self.client.discover()
        self.assertEqual(result["serverInfo"]["name"], "aegis")
        tools = self.client.list_tools()
        names = {tool["name"] for tool in tools}
        self.assertEqual(names, {
            "aegis_status", "aegis_capabilities", "aegis_plan", "aegis_inspect", "aegis_audit",
            "aegis_read_file", "aegis_search", "aegis_job", "aegis_queue",
            "desktop_observe", "desktop_screenshot", "desktop_action", "desktop_verify",
            "desktop_stop", "desktop_resume",
        })

    def test_plan_routes_without_execution(self):
        result = self.client.call_tool("aegis_plan", {"objective": "audit the trading research module"})
        payload = json.loads(result["content"][0]["text"])
        self.assertIn("routes", payload)
        self.assertEqual(payload["execution"], "not performed; submit through an explicit AEGIS approval path")

    def test_inspect_rejects_paths_outside_repository(self):
        result = self.client.call_tool("aegis_inspect", {"target": "/tmp"})
        self.assertTrue(result["isError"])

    def test_audit_is_read_only_syntax_check(self):
        result = self.client.call_tool("aegis_audit", {"target": "hermes_mcp_server.py"})
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["syntax_ok"])
        self.assertEqual(payload["mode"], "read_only_syntax_audit")

    def test_read_file_and_search_are_bounded(self):
        result = self.client.call_tool("aegis_read_file", {"target": "hermes_mcp_server.py", "max_bytes": 200})
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["truncated"])
        self.assertIn("Controlled MCP bridge", payload["content"])
        result = self.client.call_tool("aegis_search", {"query": "SafetySettings", "target": "hermes_mcp_server.py"})
        payload = json.loads(result["content"][0]["text"])
        self.assertGreaterEqual(payload["count"], 1)

    def test_queue_requires_explicit_safety_control(self):
        result = self.client.call_tool("aegis_queue", {"hostname": "penguin", "cmd": "true", "confirm": True})
        self.assertTrue(result["isError"])


if __name__ == "__main__":
    unittest.main()
