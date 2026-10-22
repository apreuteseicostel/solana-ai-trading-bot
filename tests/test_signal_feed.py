"""Offline regression tests for non-actionable SIGNAL history."""

from solana_ai_bot.signal_feed import signal_feed


def decision(**overrides):
    value = {
        "mode": "paper", "status": "filled", "side": "BUY",
        "signature": "fixture-1", "wallet": "fixture-wallet",
        "source": "synthetic_demo", "at": 100,
        "reason": "conservative_quote_simulation",
    }
    value.update(overrides)
    return value


def test_paper_fills_are_retrospective_not_buy_recommendations():
    row = signal_feed([decision()])[0]
    assert row["classification"] == "historical_paper_fill"
    assert row["side"] == "BUY"
    assert row["source"] == "synthetic_demo"
    assert row["actionable"] is False
    assert row["execution"] == "paper_only"


def test_rejections_and_unsupported_sides_do_not_become_buy_signals():
    rows = signal_feed([
        decision(status="rejected", reason="stale_quote", side=None),
        decision(side="DROP TABLE"),
        decision(mode="live"),
        {"status": "filled", "side": "BUY"},
    ])
    assert len(rows) == 2
    assert rows[0]["classification"] == "historical_rejection"
    assert rows[0]["side"] is None
    assert rows[0]["reason"] == "stale_quote"
    assert rows[1]["side"] is None
    assert all(row["actionable"] is False for row in rows)


def test_bounded_and_no_input_mutation():
    rows = [decision(signature=str(i)) for i in range(300)]
    output = signal_feed(rows)
    assert len(output) == 200
    assert output[0]["signature"] == "0"
    assert output[-1]["signature"] == "199"
    assert rows[0].get("actionable") is None


def test_requires_valid_limit():
    import pytest

    for limit in (0, 201, -1, True, 1.5):
        with pytest.raises(ValueError):
            signal_feed([decision()], limit=limit)
