"""Regression tests for bounded scanner output buffering."""
import json

from solana_ai_bot.scanner import scan_file


def test_scan_file_streams_many_records_and_deduplicates(tmp_path):
    source = tmp_path / "events.jsonl"
    target = tmp_path / "out.jsonl"
    with source.open("w", encoding="utf-8") as output:
        for index in range(1500):
            event = {"txType": "create", "mint": f"mint-{index}",
                     "traderPublicKey": "creator", "name": "Example", "symbol": "EX"}
            output.write(json.dumps(event) + "\n")
        output.write(json.dumps({"txType": "create", "mint": "mint-0",
                                 "traderPublicKey": "creator"}) + "\n")
    assert scan_file(source, target) == 1500
    with target.open(encoding="utf-8") as result:
        assert sum(1 for _ in result) == 1500
