# Pump.fun scanner v1 — local read-only event processing

This is **not yet a live Pump.fun listener**. It ingests newline-delimited JSON messages
in the shape of PumpPortal's `subscribeNewToken` event feed. It extracts creation
records, validates required fields, and deduplicates by mint in each run.

## Example

```bash
python -m pip install -e '.[dev]'
python -c "from pathlib import Path; from solana_ai_bot.scanner import scan_file; print(scan_file(Path('examples/pump_events.jsonl'), Path('events-output.jsonl')))"
pytest -q
```

The example addresses are intentionally fictional. Do not treat these as on-chain
observations or profitability signals.

## Next steps

- Verify current provider event schema against real read-only traffic.
- Add WebSocket transport with reconnection, timeouts and rate limiting.
- Persist events to SQLite with ingestion timestamps and source identifiers.
- Add historical replay, price sampling and fees/slippage modeling.
- Do not connect signing keys or live order execution.
