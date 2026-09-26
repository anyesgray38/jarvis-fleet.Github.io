import threading
import unittest

from knowledge.brain import DepartmentPlan, KnowledgeBrain


class FakeStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.data = {"sources": [], "research": {"departments": {}, "cycles": []}}
        self.saved = 0
        self.cache = {}

    def ingest_source(self, source, *, kind, manager, department, query):
        packet = {"id": f"{department}-{len(self.data['sources'])}", "department": department, "kind": kind, "title": source["title"], "query": query, "summary": "compact packet", "reverse_engineering": {"status": "verified_for_compaction"}, "promotion": {"status": "promoted_to_active_memory"}}
        self.data["sources"].append(packet)
        return packet

    def _save(self):
        self.saved += 1

    def source_is_fresh(self, url, refresh_minutes):
        return False

    def cached_search(self, query, ttl_minutes):
        return self.cache.get(query)

    def cache_search(self, query, hits):
        if hits:
            self.cache[query] = hits


class KnowledgeBrainTests(unittest.TestCase):
    def test_due_cycle_searches_and_assigns_packets_to_departments(self):
        store = FakeStore()
        brain = KnowledgeBrain(
            store,
            plans=(
                DepartmentPlan("security", "Security", "Sentinel", topics=("OWASP",), queries=("defensive security",)),
                DepartmentPlan("memory", "Memory", "Mnemia"),
            ),
            wiki_fetcher=lambda value: {"title": value, "url": "https://wiki.test/1", "content": "reference", "provider": "wikipedia"},
            web_fetcher=lambda value: {"title": value, "url": value, "content": "web research", "provider": "firecrawl-mcp"},
            web_searcher=lambda value, limit: [{"url": "https://example.test/security"}],
            max_jobs_per_cycle=4,
        )
        result = brain.run_due_cycle()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["packets"], 2)
        self.assertEqual(result["pipeline"]["promote"], 2)
        self.assertEqual({item["department"] for item in store.data["sources"]}, {"security"})
        self.assertEqual(brain.due_departments(), [])
        self.assertGreater(store.saved, 0)

    def test_failures_are_reported_as_degraded(self):
        store = FakeStore()
        brain = KnowledgeBrain(
            store,
            plans=(DepartmentPlan("web", "Web", "Atlas", queries=("broken",)),),
            wiki_fetcher=lambda value: {},
            web_fetcher=lambda value: (_ for _ in ()).throw(RuntimeError("blocked")),
            web_searcher=lambda value, limit: [{"url": "https://example.test/blocked"}],
        )
        result = brain.run_due_cycle()
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["packets"], 0)
        self.assertTrue(result["errors"])

    def test_external_call_budget_limits_search_and_scrape(self):
        store = FakeStore()
        calls = []
        brain = KnowledgeBrain(
            store,
            plans=(DepartmentPlan("web", "Web", "Atlas", queries=("one", "two")),),
            wiki_fetcher=lambda value: {},
            web_fetcher=lambda value: calls.append(value) or {"title": value, "url": value, "content": "web", "provider": "firecrawl-mcp"},
            web_searcher=lambda value, limit: [{"url": f"https://example.test/{value}"}],
            max_external_calls=1,
        )
        result = brain.run_due_cycle()
        self.assertEqual(result["external_calls"], 1)
        self.assertLessEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
