from solana_ai_bot.risk import screen_creation
from solana_ai_bot.scanner import TokenCreated


def test_screen_rejects_unverified_addresses():
    event = TokenCreated("short", "Token", "T", "short")
    result = screen_creation(event)
    assert not result.accepted
    assert "mint_length_unverified" in result.reasons


def test_screen_accepts_well_shaped_fields():
    event = TokenCreated("A" * 32, "Example", "EX", "B" * 32)
    result = screen_creation(event)
    assert result.accepted
    assert result.reasons == ()


def test_screen_rejects_control_characters():
    event = TokenCreated("A" * 32, "Bad\\nToken", "EX", "B" * 32)
    assert not screen_creation(event).accepted
