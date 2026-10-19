# Offline paper trading — SMA research baseline

The moving-average backtest is a **research baseline**, not a trading
recommendation or a profitable strategy. It never sends orders or signs
transactions and uses no live API.

## Run

```bash
python -m pip install -e '.[dev]'
solana-ai-bot backtest --prices examples/demo_price_ticks.csv --fast 2 --slow 3
```

A valid CSV has exactly `mint,timestamp,price` columns, numeric positive
mid-market prices, integer strictly increasing timestamps, and **only one mint
per file**. Sample prices and mint addresses are **fictional**. The reader
refuses mixed tokens, malformed rows and more than 100,000 observations.

The new `backtest` command emits JSON, including entry/exit times, cash,
closed-trade P&L and an **estimated** liquidation value for any open position.
The default simulation allocates at most 10% of available cash for each new
position, with 1% fee and 0.5% slippage per side (illustrative assumptions,
not verified Pump.fun costs). Use flags `--starting-cash`, `--fraction`,
`--fee-rate`, and `--slippage-rate` to inspect sensitivity.

## No look-ahead

Signals are SMA crossings computed from observed prices. A buy/sell
signal is filled **at the next observation**, never the one that produced
the signal. An open position at the end is **not** sold: its liquidation
value is only an estimate using the last observed mid price plus modeled
fees/slippage. `max_drawdown_pct` uses similarly hypothetical liquidatable
equity, not actual achievable exits.

## Critical limitations

- PumpPortal `subscribeNewToken` messages are **creation events**, not
  reliable quote histories. Do not feed them into this backtester as prices.
- The demonstration does not verify quote source, liquidity, spread, market
  impact, transaction priority fees, failed swaps, launch restrictions,
  price gaps, RPC latency, reorgs, taxes, or MEV.
- SMA is an illustrative baseline with no out-of-sample validation or
  evidence of profit. Forward testing with verified timestamped quotes is
  required before assessing performance.
- Do not put wallet keys or live trading credentials in the project.
