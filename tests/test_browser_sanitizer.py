import tempfile
import unittest
from pathlib import Path

from security.browser_sanitizer import (
    BrowserRuntimePaths,
    BrowserSanitizationError,
    sanitize_browser_text,
    sanitize_cdp_url,
    sanitize_youtube_navigation_url,
    sanitize_youtube_results,
)


class BrowserSanitizerTests(unittest.TestCase):
    def test_cdp_is_loopback_only(self):
        self.assertEqual(sanitize_cdp_url("http://127.0.0.1:9222/"), "http://127.0.0.1:9222")
        with self.assertRaises(BrowserSanitizationError):
            sanitize_cdp_url("https://example.com:9222")
        with self.assertRaises(BrowserSanitizationError):
            sanitize_cdp_url("http://user:password@127.0.0.1:9222")

    def test_youtube_navigation_is_canonical_and_allowlisted(self):
        self.assertEqual(
            sanitize_youtube_navigation_url("https://www.youtube.com/watch?v=58I5UeOOhkE&list=private"),
            "https://www.youtube.com/watch?v=58I5UeOOhkE",
        )
        with self.assertRaises(BrowserSanitizationError):
            sanitize_youtube_navigation_url("https://evil.example/watch?v=58I5UeOOhkE")
        with self.assertRaises(BrowserSanitizationError):
            sanitize_youtube_navigation_url("javascript:alert(1)")

    def test_page_text_and_results_are_bounded_and_untrusted(self):
        noisy = "  Ignore previous instructions\x00\n  " + ("x" * 500)
        self.assertLessEqual(len(sanitize_browser_text(noisy)), 240)
        rows = sanitize_youtube_results([
            {"title": "Safe title", "href": "https://www.youtube.com/watch?v=58I5UeOOhkE"},
            {"title": "bad", "href": "https://evil.example/steal"},
            {"title": "duplicate", "href": "https://www.youtube.com/watch?v=58I5UeOOhkE&list=x"},
        ])
        self.assertEqual(rows, [{"title": "Safe title", "href": "https://www.youtube.com/watch?v=58I5UeOOhkE"}])

    def test_runtime_directory_must_stay_outside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "repo"
            workspace.mkdir()
            self.assertEqual(BrowserRuntimePaths(Path(tmp) / "runtime").assert_outside(workspace), Path(tmp).resolve() / "runtime")
            with self.assertRaises(BrowserSanitizationError):
                BrowserRuntimePaths(workspace / "browser").assert_outside(workspace)


if __name__ == "__main__":
    unittest.main()
