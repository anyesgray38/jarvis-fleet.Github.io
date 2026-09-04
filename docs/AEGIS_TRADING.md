# AEGIS Trading Layer

AEGIS trading is intentionally broader than SMC. SMC is one strategy family inside a provider-neutral research system.

## Market coverage

The default research universe spans forex, metals, crypto, indices, energy, equities/ETFs, futures, options, rates, fixed income, commodities, and volatility instruments as providers are admitted.

## Strategy coverage

The catalog includes structure/SMC, trend following, mean reversion, breakouts, momentum, volatility, pairs, statistical arbitrage, carry, macro-regime, event-driven, seasonality, and order-flow research.

## Research loop

`universe -> strategy -> hypothesis -> experiment -> backtest -> walk-forward -> out-of-sample -> permutation/Monte Carlo -> regime analysis -> independent reproduction -> risk gate -> paper execution`

The system should search broadly before specializing. A strategy is not promoted because it backtests well once. AEGIS must retain provenance, test alternative explanations, measure sensitivity, and reject unstable findings.

## Execution boundary

Market-data discovery and strategy research are separated from order execution. Live broker connectivity is not enabled by this layer. Paper execution remains the default until security admission, risk controls, statistical validation, independent verification, and explicit deployment authorization are satisfied.

## Bot architecture

Each bot is an isolated strategy worker with its own configuration, risk state, signals, positions, and evidence stream. The fleet coordinator can run multiple strategy families without allowing one bot's failure to bypass portfolio-level controls.
