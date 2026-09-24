import tempfile
import unittest
from pathlib import Path

from prospecting.discovery import parse_directory_page
from prospecting.generator import generate_demo
from prospecting.geo import classify_location
from prospecting.models import BusinessRecord, ScanRequest
from prospecting.scoring import score_business
from prospecting.store import ProspectStore
from prospecting.verify import verify_static_site


DIRECTORY = """
\n+A-Nails Inc.
\n+1089 US-19
\n+Thomaston, GA 30286
\n+Phone: 706-646-2522
\n+Beauty
\n+Another Shop
\n+400 Main Street
\n+Thomaston, GA 30286
\n+Phone: 706-555-1212
"""


class ProspectingTests(unittest.TestCase):
    def test_corridor_requires_address_evidence(self):
        self.assertEqual(classify_location("1089 US-19, Thomaston, GA 30286", "US-19 Thomaston GA")[0], "DIRECTLY_ON_TARGET")
        self.assertEqual(classify_location("400 Main Street, Thomaston, GA 30286", "US-19 Thomaston GA")[0], "NEARBY")
        self.assertEqual(classify_location("400 Main Street, Macon, GA 31201", "US-19 Thomaston GA")[0], "IRRELEVANT")

    def test_directory_parser_and_deduplication(self):
        rows = parse_directory_page(DIRECTORY, "https://directory.example/list", ScanRequest("US-19 Thomaston GA"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].business_name, "A-Nails Inc.")
        self.assertEqual(rows[0].location_class, "DIRECTLY_ON_TARGET")

    def test_score_is_deterministic_and_explainable(self):
        record = BusinessRecord("biz-1", "Example", website_state="NOT_FOUND", social_profiles=[])
        first = score_business(record).opportunity_score
        second = score_business(record).opportunity_score
        self.assertEqual(first, second)
        self.assertTrue(record.score_reasons)
        self.assertEqual(record.classification, "NO_WEBSITE")

    def test_generated_demo_builds_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = BusinessRecord("biz-1", "Example Auto", address="1089 US-19, Thomaston, GA 30286", phone="706-646-2522", category="Automobile Repair", website_state="NOT_FOUND")
            generated = generate_demo(record, Path(tmp) / "scan")
            result = verify_static_site(generated["project_dir"])
            self.assertEqual(result["status"], "PASS")
            self.assertTrue((Path(generated["project_dir"]) / "index.html").exists())

    def test_store_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProspectStore(Path(tmp) / "prospects.db")
            record = BusinessRecord("biz-1", "Example")
            store.save_business(record)
            loaded = store.get_business("biz-1")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.business_name, "Example")


if __name__ == "__main__":
    unittest.main()
