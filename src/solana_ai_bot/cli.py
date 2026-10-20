"""Explicit, bounded read-only CLI for local replay and live observation."""
import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from . import intel_cli
from .backtest import BacktestConfig, run_sma_backtest
from .collector import collect_to_sqlite, replay_to_sqlite
from .market_data import load_price_csv
from .storage import TokenEventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solana-ai-bot",
        description="Read-only Pump.fun event research; never trades or signs transactions.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    replay = commands.add_parser("replay", help="Replay local event JSONL into SQLite")
    replay.add_argument("source", type=Path)
    replay.add_argument("--db", type=Path, required=True)

    stats = commands.add_parser("stats", help="Count saved creation events")
    stats.add_argument("--db", type=Path, required=True)

    listen = commands.add_parser("listen", help="Observe bounded live token events")
    listen.add_argument("--db", type=Path, required=True)
    listen.add_argument("--max-events", type=int, default=100)
    backtest = commands.add_parser("backtest", help="Offline SMA simulation on one-token CSV prices")
    backtest.add_argument("--prices", type=Path, required=True)
    backtest.add_argument("--fast", type=int, default=3)
    backtest.add_argument("--slow", type=int, default=5)
    backtest.add_argument("--starting-cash", type=float, default=1000.0)
    backtest.add_argument("--fraction", type=float, default=0.1)
    backtest.add_argument("--fee-rate", type=float, default=0.01)
    backtest.add_argument("--slippage-rate", type=float, default=0.005)
    intel_cli.add_commands(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "intel":
        return intel_cli.run(args)
    if args.command == "replay":
        observed, new = replay_to_sqlite(args.source, args.db)
        print(f"Parsed distinct events: {observed}; newly saved: {new}")
        return 0
    if args.command == "stats":
        if not args.db.is_file():
            print("Database not found.")
            return 1
        with TokenEventStore(args.db) as store:
            print(f"Stored token creations: {store.count()}")
        return 0
    if args.command == "backtest":
        mint, ticks = load_price_csv(args.prices)
        config = BacktestConfig(
            fast_window=args.fast,
            slow_window=args.slow,
            starting_cash=args.starting_cash,
            position_fraction=args.fraction,
            fee_rate=args.fee_rate,
            slippage_rate=args.slippage_rate,
        )
        result = run_sma_backtest(ticks, config)
        print(json.dumps({
            "paper_only": True,
            "source": "user_supplied_unverified_csv",
            "mint": mint,
            "observation_count": len(ticks),
            "config": asdict(config),
            "result": asdict(result),
        }, indent=2))
        return 0
    if args.max_events <= 0:
        build_parser().error("--max-events must be positive")
    print("Read-only listener. No orders, wallet keys or trading.")
    count = asyncio.run(collect_to_sqlite(args.db, max_events=args.max_events))
    print(f"Received creation events: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
