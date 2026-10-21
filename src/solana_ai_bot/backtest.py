"""Deterministic, offline moving-average paper trading simulation.

Signals use current/previous observations; fills only use the NEXT observation.
There is no live feed, transaction signer, wallet, or order router here.
"""

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PriceTick:
    timestamp: int
    price: float


@dataclass(frozen=True)
class BacktestConfig:
    fast_window: int = 3
    slow_window: int = 5
    starting_cash: float = 1000.0
    position_fraction: float = 0.1
    fee_rate: float = 0.01
    slippage_rate: float = 0.005


@dataclass(frozen=True)
class ClosedTrade:
    entered_at: int
    exited_at: int
    entry_spend: float
    exit_proceeds: float
    net_pnl: float


@dataclass(frozen=True)
class BacktestResult:
    starting_cash: float
    final_cash: float
    remaining_units: float
    estimated_liquidation_equity: float
    estimated_net_pnl: float
    max_drawdown_pct: float
    closed_trades: tuple[ClosedTrade, ...]


def _valid_number(value: object, *, positive: bool = False) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and (not positive or value > 0)
    )


def _validate(config: BacktestConfig, ticks: list[PriceTick]) -> None:
    if (
        type(config.fast_window) is not int
        or type(config.slow_window) is not int
        or not (1 <= config.fast_window < config.slow_window)
    ):
        raise ValueError("Require integer windows 1 <= fast < slow")
    if not _valid_number(config.starting_cash, positive=True):
        raise ValueError("starting_cash must be positive and finite")
    if not _valid_number(config.position_fraction, positive=True) or config.position_fraction > 1:
        raise ValueError("position_fraction must be in (0, 1]")
    for rate in (config.fee_rate, config.slippage_rate):
        if not _valid_number(rate) or not (0 <= rate < 1):
            raise ValueError("fee/slippage rates must be in [0, 1)")
    if not ticks:
        raise ValueError("At least one price observation is required")
    previous = None
    for tick in ticks:
        if type(tick.timestamp) is not int or (previous is not None and tick.timestamp <= previous):
            raise ValueError("timestamps must be strictly increasing integers")
        if not _valid_number(tick.price, positive=True):
            raise ValueError("prices must be positive and finite")
        previous = tick.timestamp


def run_sma_backtest(ticks: list[PriceTick], config: BacktestConfig | None = None) -> BacktestResult:
    """Long-only SMA crossover, filling decisions at the next observation.

    Buying spends a fixed fraction of available cash INCLUDING the buy fee.
    Selling liquidates all units and charges slippage and a sell fee.
    Open holdings are estimated at an immediate liquidation price in the
    final metric, but they are never force-sold by this simulation.
    """
    if config is None:
        config = BacktestConfig()
    _validate(config, ticks)
    cash = float(config.starting_cash)
    units = 0.0
    pending: Literal["buy", "sell"] | None = None
    previous_spread: float | None = None
    highest_equity = cash
    worst_drawdown = 0.0
    trades: list[ClosedTrade] = []
    entry_time = 0
    entry_spend = 0.0
    prices: list[float] = []

    for tick in ticks:
        mid = float(tick.price)
        if pending == "buy" and units == 0:
            spent = cash * config.position_fraction
            fill = mid * (1 + config.slippage_rate)
            units = (spent / (1 + config.fee_rate)) / fill
            cash -= spent
            entry_spend = spent
            entry_time = tick.timestamp
        elif pending == "sell" and units > 0:
            proceeds = units * mid * (1 - config.slippage_rate) * (1 - config.fee_rate)
            cash += proceeds
            trades.append(
                ClosedTrade(entry_time, tick.timestamp, entry_spend, proceeds, proceeds - entry_spend)
            )
            units = 0.0
            entry_spend = 0.0
        pending = None

        estimated_equity = cash + units * mid * (1 - config.slippage_rate) * (1 - config.fee_rate)
        highest_equity = max(highest_equity, estimated_equity)
        worst_drawdown = max(worst_drawdown, (highest_equity - estimated_equity) / highest_equity)

        prices.append(mid)
        if len(prices) >= config.slow_window:
            fast = sum(prices[-config.fast_window :]) / config.fast_window
            slow = sum(prices[-config.slow_window :]) / config.slow_window
            spread = fast - slow
            if previous_spread is not None:
                if previous_spread <= 0 < spread and units == 0:
                    pending = "buy"
                elif previous_spread >= 0 > spread and units > 0:
                    pending = "sell"
            previous_spread = spread

    liquidation_equity = cash + units * prices[-1] * (1 - config.slippage_rate) * (1 - config.fee_rate)
    return BacktestResult(
        starting_cash=float(config.starting_cash),
        final_cash=cash,
        remaining_units=units,
        estimated_liquidation_equity=liquidation_equity,
        estimated_net_pnl=liquidation_equity - config.starting_cash,
        max_drawdown_pct=worst_drawdown * 100,
        closed_trades=tuple(trades),
    )
