import asyncio

import pytest

from solana_ai_bot import collector
from solana_ai_bot.scanner import TokenCreated
from solana_ai_bot.storage import TokenEventStore


def test_collector_stores_observations(tmp_path, monkeypatch):
    async def fake_listen(on_event, **options):
        assert options["max_events"] == 2
        event = TokenCreated("Mint1", "Example", "EX", "Creator1")
        on_event(event)
        on_event(event)
        return 2

    monkeypatch.setattr(collector, "listen_new_tokens", fake_listen)
    database = tmp_path / "events.db"
    assert asyncio.run(collector.collect_to_sqlite(database, max_events=2)) == 2
    with TokenEventStore(database) as store:
        assert store.count() == 1


def test_collector_rejects_invalid_limit(tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(collector.collect_to_sqlite(tmp_path / "events.db", max_events=0))
