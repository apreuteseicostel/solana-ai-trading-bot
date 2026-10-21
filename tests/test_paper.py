import pytest

from solana_ai_bot.paper import simulate_round_trip


def test_flat_market_costs_money():
    assert simulate_round_trip(1, 1, 100).net_pnl < 0


def test_no_fees():
    r = simulate_round_trip(1, 1.2, 100, fee_rate=0, slippage_rate=0)
    assert r.net_pnl == pytest.approx(20)
    assert r.return_pct == pytest.approx(20)


def test_reject_invalid():
    with pytest.raises(ValueError):
        simulate_round_trip(0, 1, 100)
    with pytest.raises(ValueError):
        simulate_round_trip(1, 1, 100, fee_rate=1)
