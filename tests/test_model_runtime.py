import unittest
from unittest.mock import Mock, patch

from jarvis.model_service import ModelRuntime
from providers.model_router import ModelRoute


class ModelRuntimeTests(unittest.TestCase):
    def test_normalizes_openai_compatible_response(self):
        result = ModelRuntime._normalize({
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 3},
        })
        self.assertEqual(result["content"], "hello")
        self.assertEqual(result["finish_reason"], "stop")

    def test_rejects_empty_provider_response(self):
        with self.assertRaises(ValueError):
            ModelRuntime._normalize({"choices": []})

    def test_chat_records_route_and_evidence(self):
        runtime = ModelRuntime.__new__(ModelRuntime)
        runtime.fabric = Mock()
        runtime.fabric.resolve.return_value = ModelRoute(
            provider="lmstudio", model="test-model", reason="local provider preferred", score=100
        )
        runtime.fabric.chat.return_value = {
            "choices": [{"message": {"content": "test response"}, "finish_reason": "stop"}]
        }
        with patch("jarvis.model_service.ModelRuntime._write_evidence") as write:
            result = runtime.chat(messages=[{"role": "user", "content": "hello"}], purpose="general")
        self.assertTrue(result["ok"])
        self.assertEqual(result["route"]["provider"], "lmstudio")
        self.assertEqual(result["response"]["content"], "test response")
        write.assert_called_once()
        self.assertTrue(write.call_args.args[0]["verified"])


if __name__ == "__main__":
    unittest.main()
