import io
import json
from unittest.mock import patch

from knowledge.hindsight import HindsightClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self, _limit):
        return json.dumps(self.payload).encode()


def test_retain_uses_bank_endpoint_and_document_metadata():
    client = HindsightClient("http://127.0.0.1:8895")
    seen = {}
    def fake_open(req, timeout):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        return FakeResponse({"success": True})
    with patch("knowledge.hindsight.urlopen", fake_open):
        result = client.retain("repo:main", "AEGIS learned this", context="test", document_id="commit-1")
    assert result["success"] is True
    assert seen["url"].endswith("/v1/default/banks/repo%3Amain/memories")
    assert seen["body"]["async"] is True
    assert seen["body"]["items"][0]["document_id"] == "commit-1"


def test_recall_and_reflect_use_distinct_hindsight_routes():
    client = HindsightClient("http://hindsight")
    urls = []
    def fake_open(req, timeout):
        urls.append(req.full_url)
        return FakeResponse({"ok": True})
    with patch("knowledge.hindsight.urlopen", fake_open):
        client.recall("aegis-core", "what changed?")
        client.reflect("aegis-core", "what did we learn?")
    assert urls == [
        "http://hindsight/v1/default/banks/aegis-core/memories/recall",
        "http://hindsight/v1/default/banks/aegis-core/reflect",
    ]


def test_mcp_url_is_bank_scoped():
    client = HindsightClient("http://hindsight/")
    assert client.mcp_url("trading") == "http://hindsight/mcp/trading/"
