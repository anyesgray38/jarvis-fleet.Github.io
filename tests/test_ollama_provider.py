import json
import unittest
from unittest.mock import patch

from providers.ollama import OllamaConfig, OllamaProvider


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OllamaProviderTests(unittest.TestCase):
    def test_models_maps_native_tags_to_registry_shape(self):
        provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"))
        with patch("providers.ollama.urlopen", return_value=_Response({"models": [{"name": "qwen3:1.7b"}]})):
            self.assertEqual(provider.models(), [{"id": "qwen3:1.7b"}])

    def test_chat_uses_native_non_thinking_request(self):
        provider = OllamaProvider(OllamaConfig(base_url="http://127.0.0.1:11434"))
        with patch("providers.ollama.urlopen", return_value=_Response({"message": {"content": "AEGIS LOCAL LIVE"}, "done": True})) as urlopen:
            result = provider.chat(model="qwen3:1.7b", messages=[{"role": "user", "content": "ping"}], max_tokens=16)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], 16)
        self.assertEqual(result["content"], "AEGIS LOCAL LIVE")


if __name__ == "__main__":
    unittest.main()
