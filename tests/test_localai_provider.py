import unittest
from unittest.mock import patch

from providers.localai import LocalAIConfig, LocalAIProvider
from providers.model_router import ModelRouter


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        import json
        return json.dumps(self.payload).encode("utf-8")


class LocalAITests(unittest.TestCase):
    def test_chat_uses_openai_compatible_endpoint(self):
        provider = LocalAIProvider(LocalAIConfig(base_url="http://local.test"))
        with patch("providers.localai.urlopen", return_value=FakeResponse({"choices": []})) as mocked:
            provider.chat(model="local-model", messages=[{"role": "user", "content": "hello"}])
            request = mocked.call_args.args[0]
            self.assertEqual(request.full_url, "http://local.test/v1/chat/completions")
            self.assertEqual(request.method, "POST")

    def test_router_selects_localai(self):
        provider = LocalAIProvider()
        with patch.object(provider, "models", return_value=[{"id": "local-model", "tags": ["llm", "local"]}]):
            router = ModelRouter([provider])
            route = router.resolve(preferred_provider="localai", required_tags={"local"})
            self.assertEqual(route.provider, "localai")
            self.assertEqual(route.model, "local-model")


if __name__ == "__main__":
    unittest.main()
