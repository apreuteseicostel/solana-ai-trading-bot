# Market Intelligence V1 — read-only observations and paper copy experiments

## What is implemented

- Helius **Parsed Events** history, `finalized` commitment, explicit public-wallet allowlist.
- Strict public-address and atomic-integer validation. A swap needs an OK parser/transaction,
  a swap summary, the watched wallet as fee payer, and exactly matching token transfer legs.
  Transfers, ambiguous transactions, multi-asset/native SOL legs and sponsored swaps are
  recorded without generating a copy signal. This deliberately sacrifices coverage for clarity.
- SQLite observations keyed by `(wallet, signature)`, bounded pagination, durable continuation,
  and a newest-signature checkpoint advanced only after the snapshot has been drained.
  Duplicate events retain their original observation time, including across restarts.
- Jupiter **Swap V2** `GET /order` quotes with no `taker`, no transaction signing and no execution.
  Input/output mints, atomic size, response shape, impact units and minimum output are validated.
- An independently written USDC paper-copy engine: fixed-size buys, average cost accumulated
  in integer atomic units, full closure of the experiment's position on a watched sell.
  Different watched wallets maintain separate positions. This does not reconstruct whale P&L.
- An immutable configuration per run and atomic book/decision/quote updates. Reprocessing a
  signature returns the previous decision and cannot execute the simulated fill again.
- Entry limits for cash, position count, per-position/total cost exposure, realized daily losses,
  signal age, copy delay, quote age and price impact. Drawdown is measured from peak conservative
  liquidation equity and latches an entry halt. Exits still reduce exposure when entry limits
  or a drawdown halt are active, including a high-impact exit quote.
- JSON reports and an escaped, self-contained HTML dashboard **snapshot**, with paper P&L,
  costs, observed drawdown, decision reasons and explicit data-source labels.
- A bounded `watch-paper` loop combines Helius observation, quote collection, marking and paper
  decisions. It is not a deployed service or an automatically scheduled ChatGPT task.

## Quick start: no API keys, no network

```bash
python -m pip install -e '.[dev]'
python -m solana_ai_bot intel demo --db data/demo.sqlite --run-id demo --html data/demo.html
python -m solana_ai_bot intel report --db data/demo.sqlite --run-id demo --html data/demo.html
```

Open `data/demo.html`. The demonstration uses synthetic fixtures and proves only the software
path; its positive return is deliberately constructed, not evidence of strategy performance.
Repeating `demo` for the same run is idempotent. Use a new run id for a new experiment.

The console entry point `solana-ai-bot` and `python -m solana_ai_bot` now use the same CLI.

## Read-only provider access

Create provider API credentials in their official portals and set `HELIUS_API_KEY` and
`JUPITER_API_KEY` **locally as environment variables**. These are data-service credentials,
not wallet keys. The Python program does not load `.env` automatically. Never paste real
credentials into issues, commits, screenshots or chat. No wallet balance or wallet key is needed.
The installed ChatGPT plan does not provide these provider credentials or their API quotas.

Replace `PUBLIC_WALLET_ADDRESS` with the public address you explicitly want to observe:

```bash
python -m solana_ai_bot intel wallet-sync --db data/forward.sqlite --wallet PUBLIC_WALLET_ADDRESS --max-pages 3
python -m solana_ai_bot intel paper-follow --db data/forward.sqlite --wallet PUBLIC_WALLET_ADDRESS --run-id forward-v1
python -m solana_ai_bot intel report --db data/forward.sqlite --run-id forward-v1 --html data/forward.html
```

Or run a single bounded session:

```bash
python -m solana_ai_bot intel watch-paper --db data/forward.sqlite --wallet PUBLIC_WALLET_ADDRESS --run-id forward-v1 --rounds 20 --interval 15 --max-requests 100 --html data/forward.html
```

The first pass observes events; an event remains pending until the copy delay has elapsed.
Initial history is a backfill, not historical paper fills: old signals are rejected. All watched
wallet backfills must be complete before forwarding. If `resume_pending` is true, repeat sync:
it resumes the stored cursor rather than silently skipping pages. Up to 20 pages per invocation
and 1,000 continuation cursors per history snapshot are accepted; larger histories require review.

Each pass processes at most 1,000 pending events. Loops allow 1–60 rounds, intervals 5–60 seconds.
Every actual request, including retries, counts toward the session request budget. Timeouts are
10 seconds per request, at most 2 retries by default with bounded exponential backoff. Budget
exhaustion stops fetching; API unavailability cannot create a paper fill. The finite session may
end before all events are processed. Network response bodies and credential-bearing URLs are
never emitted in errors. External redirects and non-allowlisted endpoints are refused.

## Currencies, fees and honest reporting

All capital and realized P&L are denominated in **USDC**, not audited USD. USDC depeg risk is
not modelled. Token quantities remain integers in their native atomic units; no decimals lookup
or floating-point conversion is used for accounting.

- A paper fill uses Jupiter's minimum output (`otherAmountThreshold`), not the observed whale
  execution price. This models a conservative slippage envelope, not a guaranteed fill.
- Swap route fees and market impact are already reflected in the quoted output. Available
  Jupiter platform fee metadata is stored separately; it is **not subtracted twice**.
- Every filled leg deducts a configurable **estimated** network cost, default 0.01 USDC.
  It is not a measured Solana transaction fee or a complete rent/priority-fee model.
  The observed whale's fee in lamports is journalled separately and is not our simulated cost.
- Optional `extra_fee_bps` models additional user-defined costs. Slippage haircuts are recorded
  in the output token's atomic units and are never added across different tokens as if dollars.
- Provider request counts are recorded database-wide. API subscription/credit prices are
  **unknown and excluded from P&L** until billing information is supplied. Reports mark this
  explicitly, rather than reporting an invented zero API cost. Therefore P&L is not all-in net.
- Open positions require fresh, whole-position token→USDC liquidation quotes, net of the
  estimated exit cost. Equity and unrealized P&L remain `null` if any mark is missing/stale.
  Cost basis is never substituted for market value. New entries require all existing marks fresh.
- Drawdown is observed only at available valuation points. It is not continuous intrablock
  drawdown, and a stale portfolio cannot be claimed to have a verified current drawdown.

Experiment parameters are integer JSON fields. See `examples/copy_config.json`. Supply
`--config examples/copy_config.json` to paper commands on a new run; changing an existing run's
configuration is refused. A drawdown halt remains latched across restart: use a new experiment
after reviewing losses. Realized daily-loss accounting resets at UTC midnight.

## Offline replay format

`wallet-replay SOURCE --db ...` accepts bounded JSONL rows containing `wallet`, `observed_at`
and `item` (a Helius Parsed Events result). It always labels them `user_supplied_replay`.

`paper-replay SOURCE --db ... --run-id replay-v1` accepts the example in
`examples/copy_replay.jsonl`: rows hold a normalized `event`, a normalized `quote` (or null),
and `now`. Optional marking rows use `kind: "mark"`, `position_key`, `quote`, `now`.
All replay provenance is forced to `user_supplied_replay`. Forward, replay and demo observations
cannot share one paper run. A future or pre-observation quote cannot fill a signal. A supplied
replay file can fabricate times and prices: it remains unverified data, not market evidence.
Input is bounded to 10,000 JSONL rows and 256 KiB per row.

## Validation and remaining work

Deterministic tests cover parsing, pagination/resume, rejected transfers, HTTP failures/retries,
request limits, quote validation, accounting, idempotence, restarts, stale marks, source isolation,
risk limits, UTC daily reset and escaped dashboard output. Run:

```bash
ruff check .
pytest -q
```

Live Helius/Jupiter compatibility has **not** been exercised in this environment: provider keys
are absent. The first credentialed smoke test must be bounded and read-only. No wallet funding
is required. This release does not contain live order execution, wallet signing, automatic
selection of profitable whales, an AI model, rug-pull guarantees or a 3D visualization.
Forward out-of-sample evidence, actual provider cost reconciliation, pool-level liquidity and
token-security checks remain required before evaluating any claimed advantage.

Two Issue #6 input/retry defects were fixed along with this work: duplicate/ragged CSV columns
are rejected, and WebSocket reconnections retain a total retry budget plus absolute deadline.
The other Issue #6 checklist items remain open, including PumpPortal provider access,
collector quality integration, replay memory limits and verified price-history research.

## Upstream ideas and licenses

This implementation is written independently; no SolTrade, Hummingbot or Helius SDK source was
copied or vendored. It uses stdlib HTTPS against documented APIs. Concepts studied:

- Helius SDK (MIT): https://github.com/helius-labs/helius-sdk
- SolTrade (GPL-3.0): https://github.com/etcherfx/sol-trade — simulation/live parity and costs.
- Hummingbot Gateway (Apache-2.0): https://github.com/hummingbot/gateway — quote boundaries.

Provider contract references checked 20 October 2026:

- https://www.helius.dev/docs/api-reference/parsed-events/transaction-history
- https://developers.jup.ag/docs/api-reference/swap/order

The new code is a Python adapter to these services, not an installation of their TypeScript SDKs.
