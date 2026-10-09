import unittest

from prospecting.web import ResilientWebResearch
from prospecting.website_audit import audit_website


class FailingRemote:
    def search(self, *args, **kwargs):
        raise RuntimeError("remote unavailable")

    def scrape(self, *args, **kwargs):
        raise RuntimeError("remote unavailable")

    def status(self):
        return {"authenticated": True}


class HtmlRemote:
    def scrape(self, url, **kwargs):
        return {
            "url": url,
            "html": "<html><head><title>Example</title><meta name='viewport' content='width=device-width'></head><body><h1>Example</h1><a href='/contact'>Contact</a></body></html>",
            "metadata": {"statusCode": 200, "contentType": "text/html"},
            "provider": "firecrawl-mcp",
        }


class WebTransportTests(unittest.TestCase):
    def test_local_fallback_is_disabled_by_default_for_production_transport(self):
        transport = ResilientWebResearch(FailingRemote(), allow_local_fallback=False)
        transport.fallback.search = lambda *args, **kwargs: self.fail("local search fallback was used")

        with self.assertRaisesRegex(RuntimeError, "local fallback is disabled"):
            transport.search("example", limit=1)

        self.assertTrue(transport.status()["cloud_only"])
        self.assertEqual(transport.status()["fallback"], "disabled")

    def test_website_audit_uses_remote_html_when_scraper_is_supplied(self):
        audit = audit_website("https://example.test", scraper=HtmlRemote())

        self.assertTrue(audit["reachable"])
        self.assertEqual(audit["technical"]["title"], "Example")
        self.assertEqual(audit["evidence"][0]["data"]["provider"], "firecrawl-mcp")


if __name__ == "__main__":
    unittest.main()
