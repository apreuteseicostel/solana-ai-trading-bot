# solana-ai-trading-bot

Research-first Solana observations and **paper-only** trading experiments.
No wallet signing or live order execution is implemented.

```bash
python -m pip install -e '.[dev]'
python -m solana_ai_bot intel demo --db data/demo.sqlite --run-id demo --html data/demo.html
```

Open `data/demo.html` for a synthetic demonstration, not a performance claim.

- [Market Intelligence V1](docs/MARKET_INTELLIGENCE.md): Helius wallet history,
  Jupiter quote collection, USDC paper-copy experiments, risk limits and reports.
- [Read-only token scanner](docs/SCANNER.md)
- [Offline SMA backtest](docs/PAPER_BACKTEST.md)
- [Roadmap](docs/ROADMAP.md)

Development: `ruff check .` and `pytest -q`. Provider credentials are optional for offline
work and are required only for explicitly requested read-only live-data sessions.


## Paper research dashboard (priority 0)

```sh
python -m solana_ai_bot.dashboard --demo
```

Open http://127.0.0.1:8765 for an isolated synthetic demo, or pass `--db`
with an existing intelligence database. Local, read-only, no provider calls or
live execution. See [dashboard documentation](docs/WEB_DASHBOARD.md).
