"""Explicit, bounded read-only CLI for local replay and live observation."""
import argparse
import asyncio
from pathlib import Path

from .collector import collect_to_sqlite, replay_to_sqlite
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
    if args.max_events <= 0:
        build_parser().error("--max-events must be positive")
    print("Read-only listener. No orders, wallet keys or trading.")
    count = asyncio.run(collect_to_sqlite(args.db, max_events=args.max_events))
    print(f"Received creation events: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
