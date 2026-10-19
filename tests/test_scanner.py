import json

import pytest
from solana_ai_bot.scanner import parse_token_creation, read_events, scan_file


EXAMPLE = {
    "txType": "create",
    "mint": "ExampleMint111",
    "name": "Example Token",
    "symbol": "EX",
    "traderPublicKey": "ExampleCreator111",
    "signature": "ExampleSignature111",
}


def test_parse_creation():
    event = parse_token_creation(EXAMPLE)
    assert event is not None
    assert event.mint == "ExampleMint111"
    assert event.creator == "ExampleCreator111"


def test_reject_unrelated_and_invalid():
    assert parse_token_creation({**EXAMPLE, "txType": "buy"}) is None
    assert parse_token_creation({**EXAMPLE, "mint": ""}) is None
    assert parse_token_creation({"txType": "create"}) is None
    assert parse_token_creation([]) is None


def test_deduplicate_and_skip_bad_json():
    lines = ["not-json", json.dumps(EXAMPLE), json.dumps(EXAMPLE), '{"txType":"sell"}']
    assert len(list(read_events(lines))) == 1


def test_scan_file(tmp_path):
    src = tmp_path / "input.jsonl"
    dst = tmp_path / "output.jsonl"
    src.write_text(json.dumps(EXAMPLE) + "\n" + "invalid\n", encoding="utf-8")
    assert scan_file(src, dst) == 1
    assert json.loads(dst.read_text(encoding="utf-8"))["mint"] == EXAMPLE["mint"]


def test_reject_same_input_output(tmp_path):
    src = tmp_path / "input.jsonl"
    src.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        scan_file(src, src)
