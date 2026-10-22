# Priority 0: paper research web dashboard

A responsive browser interface over the intelligence SQLite book from PR #9.
It works on desktop and mobile viewport sizes. The first increment uses the
Python standard library and self-contained HTML/CSS/JavaScript, avoiding a new
Node build chain or runtime dependencies. The read API can later support React
and an authenticated FastAPI service without coupling collection to the browser.
No collector, provider request, signing, or paper-order mutation is triggered by
opening the dashboard. Existing collection commands run separately.

## Run locally

From the installed checkout (Python 3.11+):

```sh
python -m solana_ai_bot.dashboard --demo
# Or read an existing intelligence database, never a scanner-only database:
python -m solana_ai_bot.dashboard --db data/research.sqlite --port 8765
```

Open **http://127.0.0.1:8765**. `--demo` creates an isolated temporary synthetic
book and deletes it on shutdown. The demo is always labelled synthetic and never
contacts a provider. An existing database is opened with SQLite `mode=ro` and
`query_only=ON`; an absent database or run is never created by the read API.

## Four-module research suite

Adds trend-following SMA synthetic test, DCA/rebalance calculator, deterministic research brief and user-supplied SPL mint parser. Compute-only JSON POST endpoints never route orders or write SQLite; see [Research Suite](RESEARCH_SUITE.md). No verified price history, real LLM or live on-chain authority/holder/liquidity scan is connected.

## SIGNAL / PAPER AUTO increment

The dashboard now displays a non-actionable historical SIGNAL journal mapped from
recorded paper decisions, and a PAPER AUTO status panel explicitly labelled
`unknown_no_heartbeat`. These views do not initiate simulations, monitor a
background process, stream fresh market alerts or execute orders. See
[SIGNAL and PAPER AUTO](SIGNAL_PAPER_AUTO.md).

## Included

- Overview: simulated cash, realized P&L, liquidation equity and recorded drawdown.
- Experiment selection and manual refresh; no automatic polling or background work.
- Decision outcomes, searchable/filterable decision journal and visible-row JSON export.
- Paper positions with raw token quantities; no guessed token decimals.
- Database-wide wallet observation log, data provenance and provider request counts.
- Recorded immutable experiment limits. There are no settings writes.
- Empty/error states and an explicit warning when a refresh leaves an old snapshot.
- Dark responsive layout, keyboard focus, labelled controls and horizontally scrollable tables.

## API and trust boundaries

`GET /api/snapshot?run_id=...` returns a consistent SQLite read transaction, up
to 200 run names, decisions and observations, and truncation flags. Observations
and provider usage are explicitly database-wide; decisions and positions belong
to the selected run. Paper state is read as one stored JSON object, so total
response memory still depends on its size. This is a local research database,
not a hardened ingestion endpoint for arbitrary uploaded databases.

Equity is unknown if any open position has missing, stale or future marks at
the server's current time. No collector heartbeat exists: collector health is
shown as unknown rather than inferred from record counts. API billing is unknown
and excluded from simulated P&L. No invented history chart or wallet ranking is
shown. Quote provenance, profitability and provider compatibility remain unverified.

The HTTP server binds only to 127.0.0.1, checks the exact Host and Origin, has a
fixed asset allowlist, sends no CORS grants and supports no mutation endpoints.
Responses use no-store, a restrictive CSP, no external assets and no-referrer.
Untrusted strings are rendered with text nodes, never HTML templates. Request
URLs and error details are not logged. Private database paths are not returned.

**Local use only:** there is no login, TLS, internet hosting, reverse-proxy support
or multi-user isolation. Do not expose this development server through a tunnel
or bind it publicly. Mobile layout does not imply remote phone access; hosted
access requires a separate authenticated deployment design and review. Data exports
contain wallet observations and should be handled as research data.

## Validation

```sh
ruff check .
pytest -q
PYTHONPATH=src python -m unittest discover -s tests -p test_dashboard.py -v
node --check src/solana_ai_bot/web/app.js
```

The nine offline dashboard tests cover read-only behavior, missing database/run,
stale/future valuations, capped rows and run isolation, HTTP headers, hostile
Host/Origin, write refusal, fixed paths and safe errors. They run under pytest as
well as unittest. Browser rendering/accessibility and real provider smoke tests
remain manual validation work; no browser QA tool is available in this session.

## Next increments

1. Human UI/accessibility review at desktop and narrow viewport sizes.
2. Token observation view and collector heartbeat schema, with explicit provenance.
3. Separate paper-run creation workflow with validated limits and durable audit trail.
4. Authenticated backend, deployment design and PWA/offline behavior before remote use.

No wallet connection, private keys, real orders, deployment or automatic merge
is part of this dashboard increment.
