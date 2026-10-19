import json

import pytest

from solana_ai_bot import cli
from solana_ai_bot.collector import replay_to_sqlite
from solana_ai_bot.storage import TokenEventStore


EVENT = {
    "txType": "create",
    "mint": "ExampleMint111",
    "name": "Example",
    "symbol": "EX",
    "traderPublicKey": "ExampleCreator111",
}


def test_replay_is_repeatable_and_creates_directory(tmp_path, capsys):
    source = tmp_path / "events.jsonl"
    source.write_text(
        json.dumps(EVENT) + "\n" + json.dumps(EVENT) + "\n" + "bad json\n",
        encoding="utf-8",
    )
    database = tmp_path / "nested" / "events.sqlite3"
    assert cli.main(["replay", str(source), "--db", str(database)]) == 0
    assert "newly saved: 1" in capsys.readouterr().out
    assert cli.main(["replay", str(source), "--db", str(database)]) == 0
    assert "newly saved: 0" in capsys.readouterr().out
    assert cli.main(["stats", "--db", str(database)]) == 0
    assert "Stored token creations: 1" in capsys.readouterr().out
    with TokenEventStore(database) as store:
        assert store.count() == 1


def test_replay_rejects_database_as_source(tmp_path):
    path = tmp_path / "same.db"
    path.write_text("unused", encoding="utf-8")
    with pytest.raises(ValueError):
        replay_to_sqlite(path, path)


def test_stats_missing_database_does_not_create_file(tmp_path, capsys):
    path = tmp_path / "missing.db"
    assert cli.main(["stats", "--db", str(path)]) == 1
    assert "not found" in capsys.readouterr().out
    assert not path.exists()


def test_listener_defaults_are_bounded(monkeypatch, tmp_path, capsys):
    async def fake_collect(database, *, max_events):
        assert database == tmp_path / "live.db"
        assert max_events == 3
        return 3

    monkeypatch.setattr(cli, "collect_to_sqlite", fake_collect)
    assert cli.main(["listen", "--db", str(tmp_path / "live.db"), "--max-events", "3"]) == 0
    assert "Received creation events: 3" in capsys.readouterr().out


def test_listener_rejects_unbounded_or_negative_limit(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["listen", "--db", str(tmp_path / "events.db"), "--max-events", "0"])
