# SIGNAL + PAPER AUTO — initial dashboard increment

This branch adds a **read-only, retrospective SIGNAL journal**, and makes the
existing **bounded PAPER AUTO** behaviour visible in the dashboard. It does not
add order signing, live routing, background scheduling, a ranking model or
independently verified live purchase recommendations.

## SIGNAL

- The server maps up to 200 *recorded* experiment decisions from SQLite to a
  historical journal with source, side, reason, classification and timestamp.
- `historical_paper_fill` is a *simulated* historical fill, **not** a buy signal.
- Rejected decisions remain visible, not silently dropped or converted into
  opportunities. Missing source is labelled `unknown`, never inferred as live.
- Every journal row carries `actionable: false` and `execution: paper_only`.
- No network calls, market-ranking claims, wallet scoring or push alerts.

## PAPER AUTO

Existing command `intel watch-paper` performs a *bounded* Helius observation /
Jupiter quote / simulated-copy loop with risk limits. It is not started,
controlled or scheduled by this dashboard. The dashboard has no mutation
endpoints and cannot stop a separate command. The status must be displayed as
`unknown_no_heartbeat`, not `running`, even when paper decisions exist.
Experiment configuration is immutable within a run.

For a local demonstration without credentials:

```sh
python -m pip install -e '.[dev]'
python -m solana_ai_bot.dashboard --demo
```

Open http://127.0.0.1:8765 and inspect **SIGNAL history** and **PAPER AUTO
status**. Data are synthetic. For bounded research using provider credentials,
see [Market Intelligence](MARKET_INTELLIGENCE.md). Never paste keys in dashboard
fields, URLs or repository files. There is no live order execution.

## Tests and limitations

```sh
ruff check .
pytest -q
node --check src/solana_ai_bot/web/app.js
```

Historical decisions do not reveal previously unseen opportunities. Next
increment needs a separately tested candidate signal model with observation
timestamps, conservative quote/risk gates, missing-data fail-closed behaviour,
deduplication, and an independently verified out-of-sample paper run. Real
provider integration and profitability remain unverified.
