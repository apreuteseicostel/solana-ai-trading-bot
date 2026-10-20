"""Strict boundary types for read-only intelligence. Amounts are atomic integers."""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL = "So11111111111111111111111111111111111111112"
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def address(value: Any) -> str:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        raise ValueError("Expected a Solana public address")
    number = 0
    for char in value:
        if char not in BASE58:
            raise ValueError("Invalid base58 address")
        number = number * 58 + BASE58.index(char)
    leading = len(value) - len(value.lstrip("1"))
    if leading + (number.bit_length() + 7) // 8 != 32:
        raise ValueError("Address must decode to 32 bytes")
    return value


def integer(value: Any, *, positive: bool = False) -> int:
    if type(value) is int:
        result = value
    elif (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and len(value) <= 30
    ):
        result = int(value)
    else:
        raise ValueError("Expected an unsigned integer")
    if result < int(positive) or result > 2**64 - 1:
        raise ValueError("Atomic integer out of range")
    return result


def decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("Expected finite number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Expected finite number") from exc
    if not result.is_finite():
        raise ValueError("Expected finite number")
    return result


@dataclass(frozen=True)
class WalletEvent:
    wallet: str
    signature: str
    slot: int
    block_time: int
    observed_at: int
    kind: str
    reason: str
    input_mint: str = ""
    output_mint: str = ""
    input_raw: int = 0
    output_raw: int = 0
    network_fee_lamports: int = 0
    source: str = "helius_parsed_events"

    def __post_init__(self):
        address(self.wallet)
        if not isinstance(self.signature, str) or not 1 <= len(self.signature) <= 128:
            raise ValueError("Invalid signature")
        for value in (
            self.slot,
            self.block_time,
            self.observed_at,
            self.network_fee_lamports,
        ):
            if type(value) is not int:
                raise TypeError("Internal amounts and timestamps must be integers")
            integer(value)
        if self.observed_at < self.block_time:
            raise ValueError("Observation precedes block time")
        if self.kind not in {"swap", "transfer", "ignored"}:
            raise ValueError("Unknown observation kind")
        if self.kind == "swap":
            if type(self.input_raw) is not int or type(self.output_raw) is not int:
                raise TypeError("Internal atomic amounts must be integers")
            address(self.input_mint)
            address(self.output_mint)
            integer(self.input_raw, positive=True)
            integer(self.output_raw, positive=True)
            if self.input_mint == self.output_mint:
                raise ValueError("Swap must change mints")

    def record(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Quote:
    input_mint: str
    output_mint: str
    input_raw: int
    output_raw: int
    minimum_output_raw: int
    price_impact_pct: Decimal
    fetched_at: int
    slot: int
    source: str = "jupiter_v2"
    fee_bps: int = 0
    platform_fee_raw: int = 0
    platform_fee_mint: str = ""

    def __post_init__(self):
        address(self.input_mint)
        address(self.output_mint)
        for value in (self.input_raw, self.output_raw, self.minimum_output_raw):
            if type(value) is not int:
                raise TypeError("Internal atomic amounts must be integers")
            integer(value, positive=True)
        for value in (self.fetched_at, self.slot, self.fee_bps, self.platform_fee_raw):
            if type(value) is not int:
                raise TypeError("Internal quote fields must be integers")
            integer(value)
        if self.platform_fee_mint:
            address(self.platform_fee_mint)
        if self.minimum_output_raw > self.output_raw:
            raise ValueError("Invalid minimum output")
        if (
            not isinstance(self.price_impact_pct, Decimal)
            or not self.price_impact_pct.is_finite()
        ):
            raise ValueError("Invalid impact")
        if self.input_mint == self.output_mint:
            raise ValueError("Quote must change mints")

    def record(self) -> dict:
        return {**asdict(self), "price_impact_pct": str(self.price_impact_pct)}
