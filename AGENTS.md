# AGENTS.md — Solana AI Trading Bot

Repository-wide operating rules for Codex and all coding agents. These rules apply to the main branch and development branches; inspect the branch before assuming a feature has landed in main.

## Project scope
- Build a research, read-only market-data and paper-trading system for Solana, with reproducible metrics and conservative accounting.
- GitHub Issue #6 is the current audit/task backlog. Related work may exist on stacked draft PRs (#1, #4, #5, #7, #9, #10, #11); confirm actual PR state and branch bases before making changes.
- Evaluate Helius data, Jupiter quote-only integration, wallet watching, bounded collection/replay and paper-copy simulation without conflating simulations with investment returns.

## Non-negotiable trading and credential safeguards
- No live trading, transaction signing, funded-wallet operations, real order routing, auto-buy/sell or automatic execution. Do not add these capabilities as side effects of a refactor.
- No private keys, seed phrases, wallet secret material or API tokens in source, fixtures, logs, PRs or documentation. Use environment-based configuration and safe redaction.
- Read-only provider calls must be explicit, bounded by time/rate/retry budgets and fail closed. Do not assume unauthenticated PumpPortal access works until observed and documented.
- Treat simulated gains, synthetic datasets and backtest performance as illustrative only; never claim proven profitability or guaranteed returns.
- Do not change security workflows, GitHub permissions, branch protections, repository secrets or paid provider settings without explicit authorization.

## Multi-agent coordination
1. Read Issue #6, related open PRs and the implementation branch README/docs before writing code. main may contain only an initial README while implementation is on stacked PR branches.
2. Take one small, independently reviewable task. Make a dedicated branch from the correct dependency/base commit; do not accidentally start a feature from main if it depends on unmerged work.
3. Never force-push or overwrite another agent's files/branch. For overlapping tasks, communicate dependencies and affected paths through Issues/PRs.
4. Open a focused draft PR with scope, acceptance criteria, links to prerequisites, tests and unresolved limitations. No automatic merge; require human review and CI.
5. For each run, distinguish DONE, WIP and BLOCKED using evidence; do not mark an Issue checkbox complete because code was merely proposed.

## Engineering and validation
- Prefer deterministic, offline fixtures. Use mock providers to test errors, malformed events, duplicates, missing timestamps, disconnect/reconnect and cancellation.
- Enforce bounded time, memory and retry behavior. Preserve restart checkpoints, idempotency, UTC time handling and event/quote provenance.
- Reject or explicitly annotate malformed, stale, incomplete and ambiguous observations. Never manufacture prices, fills or equity when market data are missing.
- In simulations account explicitly for spreads, slippage, fees, priority/network costs, liquidity, delays, failed transactions and missing liquidation marks; report unknown costs separately.
- On branches containing the Python package, run python -m ruff check . and PYTHONPATH=src python -m pytest -q when dependencies are available; otherwise state why they could not run.
- Verify exact GitHub Actions results and commit SHA; a green run for an upstream/older branch does not validate a new branch. Never disable or bypass failing tests to force a green badge.

## Completion report
Provide the issue/PR links, base and head branches, files changed, exact test results, data-source assumptions, security implications, remaining blockers and next safe task. Never claim that backtests, replay fixtures or read-only provider checks demonstrate real-world profitability.
