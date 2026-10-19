# Pump.fun scanner — read-only research prototype

This project is **not an automated trading bot**. It can replay local JSONL
token-creation events into SQLite and contains an experimental WebSocket listener.
No signing keys, buy/sell transactions, or trade execution exist in this module.

## Install

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

For a lightweight runtime installation with the optional listener use
`python -m pip install -e ".[live]"`.

## Offline replay (safe default)

```bash
solana-ai-bot replay examples/pump_events.jsonl --db data/events.sqlite3
solana-ai-bot stats --db data/events.sqlite3
```

The example addresses are fictional. Replaying the same file again will not
insert the same mint twice. Replay counts report (a) distinct parsed events
from the input file and (b) new rows persisted to SQLite.

## Experimental real-time collection

```bash
solana-ai-bot listen --db data/events.sqlite3 --max-events 100
```

The listener subscribes only to `subscribeNewToken` through one PumpPortal
WebSocket connection at a time. It does not subscribe to metered trade feeds.
It reconnects on timeout or transport errors with an exponential delay and
stops after the configured event limit. Each successful event is committed
to SQLite. This feature has **not yet passed an end-to-end test against live
provider traffic**.

The provider may change authentication requirements and message fields. Token
creation observations require `mint` and `traderPublicKey`, with optional
`name`, `symbol`, and `signature`. Empty name/symbol means unavailable
metadata, not a verified token. The `risk.py` checks are only preliminary
data-quality checks; they are not rug-pull or security guarantees.

Provider reference: https://pumpportal.fun/data-api/real-time/

## Important limits

- No historical price, wallet performance, liquidity or rug-pull scoring yet.
- No real-money trading, order routing, wallet custody or profitability claims.
- Neither the CLI nor GitHub Actions starts a continuously running server.
- A future agent needs explicit Codex/runner integration; AGENTS.md alone
  does not launch a background agent.
