"""Connect read-only event transport to SQLite storage."""
from pathlib import Path

from .live_feed import listen_new_tokens
from .storage import TokenEventStore


async def collect_to_sqlite(
    database: Path,
    *,
    max_events: int = 100,
    url: str | None = None,
) -> int:
    """Collect at most max_events observations; duplicate mints are ignored."""
    if max_events <= 0:
        raise ValueError("max_events must be positive")
    with TokenEventStore(database) as store:
        options = {"max_events": max_events}
        if url is not None:
            options["url"] = url
        return await listen_new_tokens(store.insert, **options)
