import unittest

from trading.research import TradingResearchPlanner
from trading.strategies import find_strategies
from trading.universe import AssetClass, find_instruments


class TradingGeneralTests(unittest.TestCase):
    def test_universe_spans_multiple_asset_classes(self):
        classes = {item.asset_class for item in find_instruments()}
        self.assertGreaterEqual(len(classes), 5)
        self.assertTrue(find_instruments(asset_class=AssetClass.FOREX))
        self.assertTrue(find_instruments(tag="crypto"))

    def test_strategy_catalog_is_broader_than_smc(self):
        strategies = find_strategies()
        self.assertGreaterEqual(len(strategies), 10)
        self.assertIn("smc", {item.strategy_id for item in strategies})
        self.assertIn("mean_reversion", {item.strategy_id for item in strategies})
        self.assertIn("pairs", {item.strategy_id for item in strategies})

    def test_planner_is_bounded_and_filterable(self):
        planner = TradingResearchPlanner(max_targets=5)
        targets = planner.build(asset_class=AssetClass.FOREX)
        self.assertEqual(len(targets), 5)
        self.assertTrue(all(t.instrument.asset_class is AssetClass.FOREX for t in targets))
        self.assertEqual(len(planner.build(strategy_family="relative_value")), 5)


if __name__ == "__main__":
    unittest.main()
