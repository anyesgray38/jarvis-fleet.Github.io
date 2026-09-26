import unittest

from trading.ict_framework import DealingRange, ICTAnalyzer
from trading.bot import BotState, TradingBot
from trading.models import Candle, Direction


class ICTFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = ICTAnalyzer()

    def test_framework_coverage_matches_every_knowledge_strategy(self):
        coverage = self.analyzer.framework_coverage()
        self.assertEqual(set(coverage["strategies"]), set(self.analyzer.supported_strategy_ids()))
        self.assertEqual(coverage["foundation_gate"], ("bias", "location", "draw", "level", "time", "trigger"))
        self.assertIn("IFVG", coverage["imbalances"])
        self.assertIn("NWOG", coverage["time"])

    def test_dealing_range_premium_discount_and_ote_math(self):
        dealing_range = DealingRange(90, 110)
        self.assertEqual(dealing_range.zone(95), "discount")
        self.assertEqual(dealing_range.zone(105), "premium")
        self.assertAlmostEqual(dealing_range.retracement(95, Direction.LONG), 0.75)
        self.assertAlmostEqual(dealing_range.retracement(105, Direction.SHORT), 0.75)

    def test_fvg_ifvg_and_bpr_are_detected(self):
        candles = [
            Candle("2026-09-26T07:00:00+00:00", 100, 101, 99, 100.5),
            Candle("2026-09-26T07:05:00+00:00", 100.5, 103, 100, 102.5),
            Candle("2026-09-26T07:10:00+00:00", 102.5, 104, 102, 103.5),
            Candle("2026-09-26T07:15:00+00:00", 103.5, 104, 100.5, 101),
            Candle("2026-09-26T07:20:00+00:00", 101, 101.5, 99, 99.5),
        ]
        imbalances = self.analyzer.imbalances(candles)
        self.assertTrue(any(item.kind == "BISI" for item in imbalances))
        self.assertTrue(self.analyzer.inverted_imbalances(candles, imbalances))
        self.assertIsInstance(self.analyzer.balanced_price_ranges(imbalances), tuple)
        self.assertIsInstance(self.analyzer.volume_imbalances(candles), tuple)
        self.assertIsInstance(self.analyzer.suspension_blocks(candles), tuple)
        self.assertIsInstance(self.analyzer.vacuum_blocks(candles), tuple)

    def test_session_opening_gap_and_smt(self):
        candles = [
            Candle("2026-09-25T23:55:00+00:00", 100, 101, 99, 100),
            Candle("2026-09-26T00:05:00+00:00", 102, 103, 101, 102.5),
            Candle("2026-09-26T08:00:00+00:00", 102.5, 103, 100, 102),
        ]
        correlated = [
            Candle("2026-09-25T23:55:00+00:00", 200, 201, 199, 200),
            Candle("2026-09-26T00:05:00+00:00", 199, 200, 198, 199),
            Candle("2026-09-26T08:00:00+00:00", 199, 200, 198.5, 199.5),
        ]
        self.assertEqual(self.analyzer.session(candles[-1].timestamp), "london")
        self.assertTrue(self.analyzer.is_killzone(candles[-1].timestamp))
        self.assertTrue(self.analyzer.is_macro(candles[-1].timestamp))
        self.assertIsNotNone(self.analyzer.cbdr_range(candles))
        self.assertTrue(self.analyzer.opening_gaps(candles))
        self.assertEqual(self.analyzer.smt_divergence(candles, correlated), Direction.LONG)

    def test_framework_is_strict_when_required_step_is_missing(self):
        candles = [Candle(f"bar-{index}", 100 + index, 101 + index, 99 + index, 100.5 + index) for index in range(12)]
        report = self.analyzer.analyze("TEST", "15m", candles, "ote")
        self.assertFalse(report.valid)
        self.assertIsNone(report.signal)
        self.assertEqual(tuple(step.name for step in report.steps), ("bias", "location", "draw", "level", "time", "trigger"))

    def test_ict_analyzer_runs_through_existing_paper_bot(self):
        bot = TradingBot("TEST", "15m", analyzer=ICTAnalyzer(), strategy_id="turtle_soup")
        self.assertIsNone(bot.scan([]))
        self.assertIsNotNone(bot.last_ict_report)
        self.assertEqual(bot.state, BotState.STOPPED)
        self.assertFalse(bot.broker.live)


if __name__ == "__main__":
    unittest.main()
