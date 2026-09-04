import unittest

from trading.backtest import Backtester
from trading.bot import BotState, TradingBot
from trading.models import Candle, Direction, Signal
from trading.paper import PaperBroker
from trading.risk import RiskEngine, RiskPolicy


class TradingTests(unittest.TestCase):
    def test_risk_sizes_position_and_enforces_rr(self):
        policy = RiskPolicy(account_equity=10_000, risk_fraction=0.01, min_rr=2.0)
        engine = RiskEngine(policy)
        signal = Signal("s1", "XAUUSD", "1m", Direction.LONG, 2000, 1990, 2030, 80)
        decision = engine.size(signal)
        self.assertTrue(decision.approved)
        # The 20% notional cap limits this trade to $2,000 / $2,000 = 1 unit,
        # so realized risk is $10 rather than the uncapped $100 risk budget.
        self.assertAlmostEqual(decision.quantity, 1.0)
        self.assertAlmostEqual(decision.risk_amount, 10.0)
        bad = Signal("s2", "XAUUSD", "1m", Direction.LONG, 2000, 1990, 2010, 80)
        self.assertFalse(engine.size(bad).approved)

    def test_paper_broker_round_trip(self):
        broker = PaperBroker()
        from trading.models import OrderIntent
        order = OrderIntent("o1", "XAUUSD", Direction.LONG, 2, 2000, 1990, 2030, "s1")
        broker.submit(order)
        self.assertAlmostEqual(broker.mark("XAUUSD", 2005), 10)
        self.assertAlmostEqual(broker.close("XAUUSD", 2010), 20)

    def test_bot_stays_paper_only(self):
        bot = TradingBot("XAUUSD", "1m")
        self.assertFalse(bot.broker.live)
        self.assertEqual(bot.state, BotState.STOPPED)

    def test_backtester_empty_data_is_safe(self):
        report = Backtester().run("XAUUSD", "1m", [])
        self.assertEqual(report.trades, ())
        self.assertEqual(report.total_pnl_per_unit, 0.0)
        self.assertEqual(report.win_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
