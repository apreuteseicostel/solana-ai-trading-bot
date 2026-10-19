"""Conservative, deterministic pre-screening for token creation records.

This is a data-quality filter, not an on-chain security audit or buy signal.
"""
from dataclasses import dataclass

from .scanner import TokenCreated


@dataclass(frozen=True)
class RiskScreen:
    accepted: bool
    reasons: tuple[str, ...]


def screen_creation(event: TokenCreated) -> RiskScreen:
    reasons: list[str] = []
    if len(event.mint) < 32 or len(event.mint) > 44:
        reasons.append("mint_length_unverified")
    if len(event.creator) < 32 or len(event.creator) > 44:
        reasons.append("creator_length_unverified")
    if len(event.symbol) > 20:
        reasons.append("symbol_too_long")
    if len(event.name) > 80:
        reasons.append("name_too_long")
    if any(ord(char) < 32 for char in event.name + event.symbol):
        reasons.append("control_character")
    return RiskScreen(accepted=not reasons, reasons=tuple(reasons))
