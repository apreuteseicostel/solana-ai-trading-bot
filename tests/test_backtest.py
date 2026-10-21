import math

import pytest

from solana_ai_bot.backtest import BacktestConfig, PriceTick, run_sma_backtest


def sample_ticks():
    return [PriceTick(i, price) for i, price in enumerate([10, 9, 8, 10, 12, 14, 13, 11, 9, 8])]


def test_next_tick_fills_and_no_lookahead():
    result = run_sma_backtest(sample_ticks(), BacktestConfig(fast_window=2, slow_window=3))
    assert len(result.closed_trades) == 1
    trade = result.closed_trades[0]
    assert (trade.entered_at, trade.exited_at) == (5, 8)
    assert trade.net_pnl < 0
    assert result.remaining_units == 0
    assert result.estimated_net_pnl == pytest.approx(trade.net_pnl)


def test_fee_slippage_reduce_profit_on_same_data():
    ticks = sample_ticks()
    base = BacktestConfig(fast_window=2, slow_window=3, fee_rate=0, slippage_rate=0)
    costly = BacktestConfig(fast_window=2, slow_window=3, fee_rate=0.01, slippage_rate=0.005)
    assert run_sma_backtest(ticks, costly).estimated_net_pnl < run_sma_backtest(ticks, base).estimated_net_pnl


def test_no_cross_no_trade():
    result = run_sma_backtest([PriceTick(i, 1.0) for i in range(20)])
    assert result.closed_trades == ()
    assert result.estimated_liquidation_equity == pytest.approx(1000)


def test_open_position_has_estimated_not_realized_value():
    ticks = [PriceTick(i, p) for i, p in enumerate([10, 9, 8, 10, 12, 14, 16])]
    result = run_sma_backtest(ticks, BacktestConfig(fast_window=2, slow_window=3))
    assert result.remaining_units > 0
    assert result.closed_trades == ()
    assert result.final_cash < result.starting_cash
    assert result.estimated_liquidation_equity > result.final_cash


@pytest.mark.parametrize("prices", [[1, 0, 2], [1, float("nan")], [1, float("inf")]])
def test_bad_prices(prices):
    with pytest.raises(ValueError):
        run_sma_backtest([PriceTick(i, p) for i, p in enumerate(prices)])


@pytest.mark.parametrize("timestamps", [[1, 1], [2, 1], [True, 2]])
def test_bad_time_order(timestamps):
    with pytest.raises(ValueError):
        run_sma_backtest([PriceTick(t, 1.0) for t in timestamps])


@pytest.mark.parametrize(
    "config",
    [
        BacktestConfig(fast_window=5, slow_window=3),
        BacktestConfig(fast_window=0),
        BacktestConfig(position_fraction=0),
        BacktestConfig(position_fraction=2),
        BacktestConfig(fee_rate=-0.01),
        BacktestConfig(slippage_rate=1),
        BacktestConfig(starting_cash=math.inf),
    ],
)
def test_bad_config(config):
    with pytest.raises(ValueError):
        run_sma_backtest([PriceTick(1, 1)], config)
