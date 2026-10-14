import unittest
from unittest.mock import Mock, patch

from jarvis.model_service import ModelRuntime
from providers.model_router import ModelRoute


class ModelRuntimeTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict("os.environ", {"AEGIS_DEFAULT_MODEL": "", "AEGIS_DEFAULT_PROVIDER": "",
                                       "AEGIS_ALLOW_EXTERNAL_INFERENCE": "false"})
        env.start()
        self.addCleanup(env.stop)

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
        runtime = ModelRuntime()
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

    def test_health_distinguishes_provider_online_from_model_ready(self):
        runtime = ModelRuntime()
        provider = Mock()
        provider.provider_id = "localai"
        provider.models.return_value = []
        runtime.fabric = Mock()
        runtime.fabric.providers = [provider]
        self.assertEqual(runtime.health(), {
            "ok": True,
            "service": "aegis-model-runtime",
            "ready": False,
            "providers": [{"provider": "localai", "online": True, "models": 0}],
            "default_model": None,
            "external_inference_enabled": False,
        })

    def test_external_inference_cannot_be_enabled_by_request(self):
        runtime = ModelRuntime()
        runtime.fabric = Mock()
        with self.assertRaisesRegex(ValueError, "External paid inference is disabled"):
            runtime.chat(messages=[{"role": "user", "content": "hello"}], local_only=False,
                         allow_external=True, preferred_provider="openai")
        runtime.fabric.resolve.assert_not_called()

    def test_paid_provider_not_constructed_when_disabled_even_with_key(self):
        with patch.dict("os.environ", {"AEGIS_OPENAI_API_KEY": "test-key"}):
            runtime = ModelRuntime()
        self.assertNotIn("openai", [p.provider_id for p in runtime.fabric.providers])

    def test_health_does_not_report_other_model_as_selected_qwen_ready(self):
        runtime = ModelRuntime()
        runtime.default_model = "selected-qwen"
        provider = Mock(provider_id="localai")
        provider.models.return_value = [{"id": "old-model"}]
        runtime.fabric = Mock()
        runtime.fabric.providers = [provider]
        runtime.fabric.registry.candidate_map.return_value = {"old-model": object(), "selected-qwen": object()}
        self.assertFalse(runtime.health()["ready"])
        provider.models.return_value = [{"id": "selected-qwen"}]
        self.assertTrue(runtime.health()["ready"])

    def test_default_model_is_sent_to_router(self):
        runtime = ModelRuntime()
        runtime.default_model = "selected-qwen"
        runtime.fabric = Mock()
        runtime.fabric.resolve.side_effect = LookupError("not available")
        with self.assertRaises(LookupError):
            runtime.chat(messages=[{"role": "user", "content": "hello"}], local_only=False)
        request = runtime.fabric.resolve.call_args.kwargs["request"]
        self.assertEqual(request.preferred_model, "selected-qwen")
        self.assertTrue(request.local_only)


if __name__ == "__main__":
    unittest.main()
