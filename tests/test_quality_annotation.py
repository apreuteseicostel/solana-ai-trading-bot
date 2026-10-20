"""Regression tests: quality annotations must not silently discard observations."""
from solana_ai_bot.collector import annotate_quality
from solana_ai_bot.scanner import TokenCreated


def test_quality_annotation_marks_bad_metadata():
    event = TokenCreated("short", "Token", "T", "short")
    result = annotate_quality(event)
    assert result.accepted is False
    assert "mint_length_unverified" in result.reasons


def test_quality_annotation_accepts_well_shaped_metadata():
    event = TokenCreated("A" * 32, "Token", "T", "B" * 32)
    result = annotate_quality(event)
    assert result.accepted is True
    assert result.reasons == ()
