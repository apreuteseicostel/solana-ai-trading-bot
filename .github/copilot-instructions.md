# GitHub Copilot instructions — Solana AI Trading Bot

## Project and current maturity
This Python 3.11 project researches Solana/Pump.fun token-creation events and offline paper-trading simulations. It is NOT approved for, or capable of, safe live trading. Treat it as a research prototype, not a profitable strategy. Read `AGENTS.md`, `docs/ROADMAP.md`, and relevant design docs before making changes.

Current stacked development branches/PRs:
- PR #1: project foundation, simulation arithmetic and CI.
- PR #4: read-only PumpPortal-style ingestion, SQLite and CLI.
- PR #5: offline SMA backtester with cost assumptions.
These PRs are Draft and depend on one another. Do not assume features are merged to `main`.

## Development workflow
- For new work, prioritize Issue #6: https://github.com/apreuteseicostel/solana-ai-trading-bot/issues/6.
- Inspect the current branch, relevant issue and tests before editing. Make focused changes on a new feature branch from the appropriate development branch.
- Use Python 3.11. Install with `python -m pip install -e '.[dev]'`; validate with `ruff check .` and `pytest -q`.
- Add deterministic tests, especially for malformed data, WebSocket disconnections, state handling and input limits. Mock external streams in automated tests.
- Describe files changed, test command/results, security concerns and what remains unvalidated. Propose a Draft PR; do not merge without explicit user approval.
- Keep API/backend formats compatible when possible. Do not claim a build, test, API call or GitHub action succeeded unless you observed its result.

## Security and financial boundaries — mandatory
- Never ask for, generate, log, transmit or commit private keys, seed phrases, wallet signing material or live order credentials.
- Never create or enable live buying, selling, signing, swap submission or unattended trade execution.
- Do not connect to production wallets, use real funds or change repository access/permissions.
- Do not disable lint/tests/security checks, leak secrets to logs, or run unreviewed third-party scripts.
- Treat token metadata, contract addresses, websocket messages, wallet rankings and quoted profit data as untrusted.
- Keep HTTP/WebSocket interactions read-only, bounded by timeouts/retry limits and independently reviewable.
- Do not interpret a data-quality filter as proof against honeypots, scams or rug pulls.
- No claims about profitability without audited price sources and robust out-of-sample or forward results.

## Repository structure
- `src/solana_ai_bot/scanner.py`: token creation event parsing.
- `src/solana_ai_bot/live_feed.py`: experimental read-only WebSocket listener.
- `src/solana_ai_bot/collector.py` and `storage.py`: event replay and SQLite.
- `src/solana_ai_bot/risk.py`: preliminary input-quality checks only.
- `src/solana_ai_bot/backtest.py` and `market_data.py`: offline price-series simulation, not on-chain prices.
- `src/solana_ai_bot/cli.py`: replay, stats, listen and backtest commands.
- `tests/`: regression tests; `.github/workflows/`: CI and dependency audit.

## First suggested task
After verifying the branch and Issue #6, investigate reconnect handling in `live_feed.py`. Add deterministic tests for repeated successful handshakes followed by disconnections. Ensure retries have a bounded budget even in that case. Do not modify the public network endpoint or introduce an API token without reviewing official provider documentation.
