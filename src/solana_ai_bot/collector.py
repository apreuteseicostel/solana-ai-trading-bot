"""Read-only event collection and deterministic fixture replay."""
from pathlib import Path

from .live_feed import listen_new_tokens
from .scanner import read_events
from .storage import TokenEventStore


def replay_to_sqlite(source: Path, database: Path) -> tuple[int, int]:
    """Replay local JSONL events and return (valid distinct events, newly stored).

    Input files are streaming rather than materialized in memory. This function
    performs no network requests, wallet signing or trading.
    """
    if source.resolve() == database.resolve():
        raise ValueError("The source JSONL and SQLite database must differ")
    parsed = 0
    inserted = 0
    with source.open("r", encoding="utf-8") as lines:
        with TokenEventStore(database) as store:
            for event in read_events(lines):
                parsed += 1
                if store.insert(event):
                    inserted += 1
    return parsed, inserted


async def collect_to_sqlite(
    database: Path,
    *,
    max_events: int = 100,
    url: str | None = None,
) -> int:
    """Collect at most max_events observations; duplicate mints are ignored."""
    if max_events <= 0:
        raise ValueError("max_events must be positive")
    database.parent.mkdir(parents=True, exist_ok=True)
    with TokenEventStore(database) as store:
        options = {"max_events": max_events}
        if url is not None:
            options["url"] = url
        return await listen_new_tokens(store.insert, **options)
