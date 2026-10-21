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
