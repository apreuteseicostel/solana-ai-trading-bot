"""Persist data-quality flags without confusing them with fraud detection."""
import asyncio
import json
import sqlite3

import pytest

from solana_ai_bot import collector
from solana_ai_bot.risk import RiskScreen
from solana_ai_bot.scanner import TokenCreated
from solana_ai_bot.storage import TokenEventStore


def test_replay_persists_annotations_without_filtering(tmp_path):
    source = tmp_path / "events.jsonl"
    bad = {"txType": "create", "mint": "short", "traderPublicKey": "short",
           "name": "Example", "symbol": "EX"}
    good = {"txType": "create", "mint": "A" * 32, "traderPublicKey": "B" * 32,
            "name": "Example", "symbol": "EX"}
    source.write_text("\n".join(json.dumps(x) for x in (bad, good)) + "\n", encoding="utf-8")
    db = tmp_path / "tokens.sqlite3"
    assert collector.replay_to_sqlite(source, db) == (2, 2)
    assert collector.replay_to_sqlite(source, db) == (2, 0)
    with TokenEventStore(db) as store:
        assert store.count() == 2
        assert store.get_quality("short") == RiskScreen(
            False, ("mint_length_unverified", "creator_length_unverified"))
        assert store.get_quality("A" * 32) == RiskScreen(True, ())
        assert store.get_quality("missing") is None


def test_legacy_row_backfill_does_not_replace_first_annotation(tmp_path):
    event = TokenCreated("short", "Example", "EX", "short")
    with TokenEventStore(tmp_path / "db.sqlite3") as store:
        assert store.insert(event)
        assert store.get_quality("short") is None
        assert not store.insert(event, quality=RiskScreen(False, ("metadata_unverified",)))
        assert not store.insert(event, quality=RiskScreen(True, ()))
        assert store.get_quality("short") == RiskScreen(False, ("metadata_unverified",))
        assert store.count() == 1


def test_annotation_error_rolls_back_observation(tmp_path):
    event = TokenCreated("short", "Example", "EX", "short")
    with TokenEventStore(tmp_path / "db.sqlite3") as store:
        store.connection.execute("""CREATE TRIGGER reject_quality BEFORE INSERT
            ON token_quality_annotations BEGIN SELECT RAISE(ABORT, 'test error'); END""")
        with pytest.raises(sqlite3.IntegrityError):
            store.insert(event, quality=RiskScreen(False, ("bad",)))
        assert store.count() == 0


def test_live_callback_persists_quality(tmp_path, monkeypatch):
    async def fake_listen(on_event, **options):
        assert options["max_events"] == 1
        assert on_event(TokenCreated("short", "Example", "EX", "short"))
        return 1

    monkeypatch.setattr(collector, "listen_new_tokens", fake_listen)
    db = tmp_path / "db.sqlite3"
    assert asyncio.run(collector.collect_to_sqlite(db, max_events=1)) == 1
    with TokenEventStore(db) as store:
        assert store.count() == 1
        assert store.get_quality("short").accepted is False
