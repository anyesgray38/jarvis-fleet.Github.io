import unittest

from jarvis.shark_context import apply_context, load_context


class SharkContextTests(unittest.TestCase):
    def test_general_context_is_core_only(self):
        context = load_context("general")
        self.assertIn("SHARK AI — LEAN CORE", context)
        self.assertNotIn("SHARK PENTEST PROFILE", context)

    def test_removed_offensive_purpose_loads_no_special_profile(self):
        context = load_context("offensive-security")
        self.assertIn("SHARK AI — LEAN CORE", context)
        self.assertNotIn("SHARK SECURITY PROFILE", context)
        self.assertNotIn("SHARK PENTEST PROFILE", context)
        self.assertNotIn("SHARK CODING PROFILE", context)

    def test_apply_context_does_not_mutate_user_messages(self):
        messages = [{"role": "user", "content": "inspect this"}]
        result = apply_context(messages, "coding")
        self.assertEqual(messages, [{"role": "user", "content": "inspect this"}])
        self.assertEqual(result[0]["role"], "system")
        self.assertIn("SHARK CODING PROFILE", result[0]["content"])


if __name__ == "__main__":
    unittest.main()
