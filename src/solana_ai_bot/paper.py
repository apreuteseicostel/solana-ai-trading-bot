"""Paper trading without any blockchain transaction signing."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TradeResult:
    gross_pnl: float
    fees: float
    net_pnl: float
    return_pct: float


def simulate_round_trip(entry_price: float, exit_price: float, stake: float,
                        fee_rate: float = 0.01, slippage_rate: float = 0.005) -> TradeResult:
    """Apply illustrative fees and slippage to both buy and sell."""
    if min(entry_price, exit_price, stake) <= 0:
        raise ValueError("Prices and stake must be positive")
    if not (0 <= fee_rate < 1 and 0 <= slippage_rate < 1):
        raise ValueError("Rates must be in [0, 1)")
    buy_fill = entry_price * (1 + slippage_rate)
    sell_fill = exit_price * (1 - slippage_rate)
    proceeds = (stake / buy_fill) * sell_fill
    fees = fee_rate * (stake + proceeds)
    pnl = proceeds - stake
    return TradeResult(pnl, fees, pnl - fees, 100 * (pnl - fees) / (stake + stake * fee_rate))
