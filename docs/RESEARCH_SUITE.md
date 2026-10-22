# Research Suite: trend, DCA/rebalance, reports and token scanner

This is a **locally bound, read-only research dashboard**, stacked on the
SIGNAL/PAPER AUTO dashboard branch (PR #15). All four modules are research
utilities. No wallet signing, order routing, network ingestion, chat model
or automated execution is added. Open the local dashboard:

```sh
python -m pip install -e '.[dev]'
python -m solana_ai_bot.dashboard --demo
# Browser: http://127.0.0.1:8765
```

`--demo` makes a temporary book of **synthetic**, clearly-labelled data.

## 1. Trend-following

Reuses the repository's `run_sma_backtest` next-observation-fill engine with a
fixed 24-tick synthetic fixture (SMA 3/6). Returns illustrative estimated
equity, P&L, historical trend and drawdown. For non-synthetic books the UI
shows **NO VERIFIED PRICE SERIES**, not a fabricated market signal.
Trading, Freqtrade, price streaming, plotting the full equity history and
risk-validated market execution are not wired up. Current engine models a
simple fee/slippage assumption; network/priority fees and failed fills remain
outside the example.

Freqtrade/FreqUI is a potential CEX subsystem, *not* a drop-in Solana
pump.fun/Jupiter execution engine. Avoid mixing CEX and on-chain accounting.

## 2. DCA / rebalancing

Local-only compute endpoint: `POST /api/dca/preview` with JSON:

```json
{
  "holdings": {"SOL": "400", "USDC": "600"},
  "targets": {"SOL": "50", "USDC": "50"},
  "contribution_usdc": "100",
  "mode": "dca"
}
```

- `dca` allocates the contributed cash proportionally to target
  underweights, *without* hypothetical sells.
- `rebalance` returns hypothetical target-weight buy/sell deltas.
- Values are entered **in USDC equivalents by the user**, not extracted
  from wallets or an order book. Inputs are bounded, finite, nonnegative,
  rounded to cents; target weights sum to 100%.
- Rounding can leave a small cent residual, reported in `planned_net_usdc`.
- Prices, commissions, spreads, taxes, priority/network fees and liquidity
  are unknown. No scheduled DCA service, rebalance worker or real order API.

## 3. Research assistant

The assistant page uses the selected read-only SQLite snapshot to build a
**deterministic** summary of recorded paper decisions and data provenance.
It does NOT call a large language model, summarize current news, run chat,
send alerts or place trades.

To enable an actual LLM later, design a separate server-side bounded job,
with explicit per-day cost limits, caching, document provenance, redaction
of provider keys, stored timestamped reports and human-only order approval.
Never permit model responses to invoke a wallet signer or order router.

## 4. Token scanner

`POST /api/token/inspect` accepts a Solana mint address and optionally
the JSON body of a *user-supplied* `getAccountInfo` result requested with
`encoding=jsonParsed`. It validates a 32-byte base58 mint and the
SPL Token or Token-2022 parsed mint account fields.

It reports *claimed* mint and freeze authorities with
`provenance=user_supplied_unverified_jsonparsed_rpc`. A pasted RPC response
can be fabricated, so these are **not independently verified on-chain facts**.
Without supplied evidence it returns **unknown**. Holder distribution and
liquidity depth always remain unknown in this increment. Mint/freeze authority
absence alone cannot establish token safety; Token-2022 extensions must also
be evaluated. No token is labelled `safe` or `buy`.

Later production scanner: verified allowlisted RPC `getAccountInfo`,
`getTokenLargestAccounts`/supply checks, audited liquidity pool evidence,
freshness, source trace and a budgeted cache. RPC `getAccountInfo` is
read-only; don't expose arbitrary provider URL input.

## Backend safety

Both POST endpoints are **compute-only**. The local HTTP server accepts
them only on the expected 127.0.0.1 host, rejects cross-origin requests,
requires JSON and bounds the body to 16 KiB. They do not write SQLite,
start workers or contact external providers. All other POST requests remain
unavailable. Do not expose the server on a public host or tunnel.

## Validation

```sh
ruff check .
pytest -q
node --check src/solana_ai_bot/web/app.js
```

CI currently covers Python lint, tests and dependency audits. Human browser
QA, JS syntax check, accessibility and live provider smoke tests remain
separate checks; do not mark them green without real execution.

## Future stages (not implemented)

1. Verified price histories with provenance and out-of-sample strategy tests;
   risk-aware prospective SIGNAL scoring and a genuine forward PAPER AUTO worker.
2. Durable *paper-only* DCA scheduling, audit trail and quote-cost simulator.
3. Server-side LLM cache / cost quotas, consent and timestamped report storage.
4. Provider-authenticated read-only mint, holder and liquidity scanning.
5. Security review and profitability validation; live execution would need an
   explicit separate project approval and is intentionally prohibited here.
