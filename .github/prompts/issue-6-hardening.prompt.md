---
agent: 'agent'
description: 'Safely implement one audited fix from Solana Issue #6'
---

Work in repository `apreuteseicostel/solana-ai-trading-bot`. Read `AGENTS.md`, `.github/copilot-instructions.md`, and Issue #6 at
https://github.com/apreuteseicostel/solana-ai-trading-bot/issues/6.

This is a security-sensitive, **offline/paper trading only** research project. Start by examining the current checked-out branch and existing tests. Do not act on `main`. Never access wallet keys, place real trades, create live order execution, merge PRs, or disable validation.

**First task:** audit `src/solana_ai_bot/live_feed.py`: its retry count resets on each successful handshake and may allow indefinite reconnections if the server immediately disconnects. Propose and implement a minimal, well-tested bounded retry policy. Add offline/mock tests covering repeated connect-close cycles, timeout/transport errors and successful bounded collection. Do not make real network connections in CI.

Run `ruff check .` and `pytest -q`, correct failures attributable to your changes, and report actual results. Stop before any commit or push unless I explicitly approve them in this Copilot session. Summarize exact changed files, outstanding risks and suggested draft PR description. If required tools are unavailable, explain the blocker instead of claiming success.
