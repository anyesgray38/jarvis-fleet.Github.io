import unittest

from trading.ict_knowledge import foundation_sequence, load_ict_knowledge, strategy_rules, term_definition, term_definitions


class ICTKnowledgeTests(unittest.TestCase):
    def test_foundation_sequence_matches_book_framework(self):
        self.assertEqual(foundation_sequence(), ("bias", "location", "draw", "level", "time", "trigger"))

    def test_liquidity_is_preserved_as_narrative_target(self):
        data = load_ict_knowledge()
        self.assertEqual(data["framework"]["liquidity_first_interpretation"]["liquidity"], "narrative and target")

    def test_turtle_soup_targets_opposite_liquidity(self):
        rules = strategy_rules("turtle_soup")["rules"]
        self.assertIn("target opposite range liquidity", rules)

    def test_every_local_ict_definition_has_meaning_and_function(self):
        definitions = term_definitions()
        self.assertGreaterEqual(len(definitions), 80)
        self.assertTrue(all(item.get("meaning") and item.get("function") for item in definitions.values()))

    def test_definition_lookup_supports_plain_language_aliases(self):
        self.assertTrue(term_definition("MSS")["meaning"].startswith("Market Structure Shift"))
        self.assertTrue(term_definition("fair value gap")["function"].startswith("Provides an imbalance"))
        self.assertTrue(term_definition("order_block")["meaning"].startswith("A retest model"))


if __name__ == "__main__":
    unittest.main()
