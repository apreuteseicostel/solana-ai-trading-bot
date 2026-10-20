"""Offline, single-mint price observations supplied explicitly by the user.

Pump.fun token creation messages do NOT contain tradable price histories.
"""

import csv
from pathlib import Path

from .backtest import PriceTick


def load_price_csv(path: Path, *, max_rows: int = 100_000) -> tuple[str, list[PriceTick]]:
    """Load timestamp/price/mint rows, refusing mixed tokens and oversized files."""
    if type(max_rows) is not int or max_rows <= 0:
        raise ValueError("max_rows must be positive")
    ticks: list[PriceTick] = []
    current_mint: str | None = None
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if (reader.fieldnames is None or len(reader.fieldnames) != 3
                or set(reader.fieldnames) != {"mint", "timestamp", "price"}):
            raise ValueError("CSV requires exactly: mint,timestamp,price")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV row must match its three columns exactly")
            if len(ticks) >= max_rows:
                raise ValueError("CSV exceeded max_rows")
            mint = row.get("mint")
            if not isinstance(mint, str) or not mint.strip() or len(mint) > 256:
                raise ValueError("Invalid mint in CSV")
            if current_mint is None:
                current_mint = mint
            elif mint != current_mint:
                raise ValueError("CSV must contain only one token mint")
            try:
                timestamp = int(row["timestamp"])
                price = float(row["price"])
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError("Invalid timestamp or price in CSV") from exc
            ticks.append(PriceTick(timestamp, price))
    if not ticks:
        raise ValueError("Price CSV has no observations")
    return current_mint, ticks
