from solana_ai_bot.scanner import TokenCreated
from solana_ai_bot.storage import TokenEventStore


def test_store_deduplicates(tmp_path):
    event = TokenCreated(
        mint="ExampleMint111",
        name="Test token",
        symbol="TEST",
        creator="Creator111",
        signature="Signature111",
    )
    path = tmp_path / "tokens.sqlite3"
    with TokenEventStore(path) as store:
        assert store.insert(event)
        assert not store.insert(event)
        assert store.count() == 1
    with TokenEventStore(path) as reopened:
        assert reopened.count() == 1


def test_store_handles_untrusted_text(tmp_path):
    event = TokenCreated(
        mint="x'); DROP TABLE token_creations; --",
        name="malicious-looking text",
        symbol="T",
        creator="Creator",
    )
    with TokenEventStore(tmp_path / "test.sqlite3") as store:
        assert store.insert(event)
        assert store.count() == 1
