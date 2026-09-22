import json
import unittest
from unittest.mock import patch

from providers.openai_compatible import OpenAICompatibleConfig, OpenAICompatibleProvider


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OpenAIProviderTests(unittest.TestCase):
    def test_uses_openai_v1_endpoint_and_bearer_secret(self):
        provider = OpenAICompatibleProvider(
            "openai",
            OpenAICompatibleConfig(base_url="https://api.openai.com/", api_key="test-key"),
        )
        with patch("providers.openai_compatible.urlopen", return_value=_Response({"data": [{"id": "gpt-5-mini"}]})) as urlopen:
            models = provider.models()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/models")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(models, [{"id": "gpt-5-mini"}])

if __name__ == "__main__":
    unittest.main()
