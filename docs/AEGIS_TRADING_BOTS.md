# AEGIS Trading + Bot Layer

The first trading implementation is deliberately **paper-first**. It provides deterministic SMC feature extraction, confluence scoring, risk admission, paper execution, multi-bot coordination, and a backtest harness.

## Pipeline

```text
Market data
  -> Candle contracts
  -> SMC feature extraction
     -> liquidity sweep
     -> FVG
     -> displacement
     -> structure-shift confirmation
  -> Confluence score
  -> Risk gate
  -> Paper order
  -> Position state
  -> Evidence / audit
  -> Research ledger
```

### Trading bots

The initial fleet is configured for:

- XAUUSD 1m SMC
- XAGUSD 3m SMC
- BTCUSD 3m SMC

These are research/paper bots. They do not contain broker credentials or live-order authority.

## Strategy model

AEGIS treats liquidity as the narrative/target layer. A liquidity sweep is distinct from a structure shift; displacement is confirmation of intent; FVGs are confluence inputs rather than automatic entries. The analyzer therefore emits an explainable score and reasons instead of a binary claim that a setup is predictive.

## Risk model

The MVP defaults to 0.5% account risk per admitted trade, a 20% notional cap, 2R minimum reward/risk, and a 2% daily realized-loss stop. Position sizing is derived from stop distance rather than a fixed lot size.

## Research requirements

Before a strategy can be promoted from research to live execution, AEGIS should require:

1. Historical data provenance.
2. In-sample/backtest results.
3. Walk-forward or out-of-sample validation.
4. Independent reproduction.
5. Slippage, spread, and execution-cost sensitivity.
6. Risk-limit validation.
7. Self-audit and evidence completeness.
8. Explicit broker capability admission and approval.

Live execution is disabled in `trading/bots.json` and is not implemented by the paper broker.
