"""Offline research suite acceptance and fail-closed tests."""

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from solana_ai_bot.copy_paper import CopyPaper
from solana_ai_bot.dashboard import handler_for, snapshot
from solana_ai_bot.intel_cli import demo
from solana_ai_bot.intel_store import IntelStore
from solana_ai_bot.research_suite import (
    dca_preview,
    inspect_token,
    research_brief,
    trend_research,
)

MINT = "11111111111111111111111111111111"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def test_synthetic_trend_uses_existing_sma_backtest():
    row = trend_research("synthetic_demo")
    assert row["available"] is True
    assert row["data_source"] == "synthetic_demo_fixed_prices"
    assert row["prices_count"] == 24
    assert row["orders_submitted"] is False
    assert row["closed_paper_trades"] >= 0


@pytest.mark.parametrize("source", [None, "", "helius_parsed_events", "user_supplied_replay"])
def test_real_or_unknown_sources_do_not_receive_fake_trend(source):
    row = trend_research(source)
    assert row["available"] is False
    assert row["data_source"] == "unavailable"
    assert row["orders_submitted"] is False


def test_dca_does_not_sell_overweights():
    r = dca_preview({
        "holdings": {"SOL": "800", "USDC": "200"},
        "targets": {"SOL": "50", "USDC": "50"},
        "contribution_usdc": "100", "mode": "dca",
    })
    values = {a["asset"]: a for a in r["rows"]}
    assert values["SOL"]["delta_usdc"] == "0.00"
    assert values["USDC"]["delta_usdc"] == "100.00"
    assert r["orders_submitted"] is False
    assert r["execution_costs_usdc"] is None


def test_rebalance_includes_hypothetical_sell_and_buy():
    r = dca_preview({
        "holdings": {"SOL": "800", "USDC": "200"},
        "targets": {"SOL": "50", "USDC": "50"},
        "contribution_usdc": "0", "mode": "rebalance",
    })
    values = {a["asset"]: a["delta_usdc"] for a in r["rows"]}
    assert values == {"SOL": "-300.00", "USDC": "300.00"}
    assert r["planned_net_usdc"] == "0.00"


@pytest.mark.parametrize("payload", [
    {"holdings": {"SOL": 100}, "targets": {"SOL": 99}},
    {"holdings": {"SOL": 100}, "targets": {"USDC": 100}},
    {"holdings": {"SOL": True}, "targets": {"SOL": 100}},
    {"holdings": {"SOL": -1}, "targets": {"SOL": 100}},
    {"holdings": {"SOL": "NaN"}, "targets": {"SOL": 100}},
    {"holdings": {"SOL": "1.234"}, "targets": {"SOL": 100}},
    {"holdings": {"SOL": 100}, "targets": {"SOL": 100}, "mode": "trade"},
    {"holdings": {"SOL": 100}, "targets": {"SOL": 100}, "seed": "secret"},
    {},
])
def test_dca_invalid_inputs_fail_closed(payload):
    with pytest.raises((ValueError, TypeError)):
        dca_preview(payload)


def test_token_inspection_without_evidence_never_claims_safety():
    r = inspect_token({"mint": MINT})
    assert r["authority_check"] == "unknown"
    assert r["liquidity_depth_usdc"] is None
    assert r["top_holders_pct"] is None
    assert r["mint_authority_active"] is None
    assert r["freeze_authority_active"] is None
    assert r["orders_submitted"] is False


def test_token_inspection_parses_user_supplied_json_as_unverified():
    sample = {
        "result": {"value": {
            "owner": TOKEN_PROGRAM,
            "data": {"parsed": {"type": "mint", "info": {
                "mintAuthority": MINT, "freezeAuthority": None,
                "decimals": 6, "supply": "123456",
            }}},
        }}
    }
    row = inspect_token({"mint": MINT, "rpc_response": sample})
    assert row["authority_check"] == "parsed_unverified"
    assert row["mint_authority_active"] is True
    assert row["freeze_authority_active"] is False
    assert row["liquidity_depth_usdc"] is None
    assert row["top_holders_pct"] is None
    assert row["provenance"] == "user_supplied_unverified_jsonparsed_rpc"


@pytest.mark.parametrize("evidence_case", [
    {"mint": "invalid!"},
    {"mint": MINT, "rpc_response": []},
    {"mint": MINT, "rpc_response": {"result": {"value": None}}},
    {"mint": MINT, "rpc_response": {"result": {"value": {
        "owner": "unexpected", "data": {"parsed": {"type": "mint", "info": {}}},
    }}}},
])
def test_token_invalid_evidence_fails_closed(evidence_case):
    with pytest.raises((ValueError, TypeError)):
        inspect_token(evidence_case)


class FakeConnection:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = bytearray()

    def makefile(self, *_args):
        return self.input

    def sendall(self, payload):
        self.output.extend(payload)


def local_request(database, path, payload, *, origin=None, method="POST"):
    body = json.dumps(payload).encode()
    h = ("POST " if method == "POST" else "GET ") + path + " HTTP/1.1\r\n"
    h += "Host: 127.0.0.1:8765\r\n"
    if origin is not None:
        h += f"Origin: {origin}\r\n"
    h += f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
    connection = FakeConnection(h.encode() + body)
    handler_for(database)(connection, ("127.0.0.1", 11000),
                          SimpleNamespace(server_port=8765))
    headers, data = bytes(connection.output).split(b"\r\n\r\n", 1)
    return headers.decode(), json.loads(data)


def test_http_preview_and_scanner_are_read_only(tmp_path: Path):
    path = tmp_path / "research.sqlite"
    with IntelStore(path) as store:
        when = demo(CopyPaper(store, "synthetic-demo"))
    before = path.read_bytes()
    headers, response = local_request(path, "/api/dca/preview", {
        "holdings": {"SOL": "400", "USDC": "600"},
        "targets": {"SOL": "50", "USDC": "50"},
        "contribution_usdc": "100",
    })
    assert "200 OK" in headers
    assert response["preview_only"] is True
    assert response["orders_submitted"] is False
    headers, response = local_request(path, "/api/token/inspect", {"mint": MINT})
    assert "200 OK" in headers
    assert response["authority_check"] == "unknown"
    assert snapshot(path, now=when)["research"]["brief"]["external_llm_connected"] is False
    assert path.read_bytes() == before


def test_http_rejects_writes_and_cross_origin(tmp_path):
    path = tmp_path / "none.db"
    body = {"mint": MINT}
    assert "501" in local_request(path, "/api/snapshot", body)[0]
    assert "403" in local_request(path, "/api/token/inspect", body,
                                  origin="https://evil.example")[0]
    assert "400" in local_request(path, "/api/token/inspect", {"mint": "bad!"})[0]


def test_brief_is_factual_rules_not_llm():
    book = {"run_id": "demo", "equity_raw": None,
            "state": {"dataset_mode": "synthetic_demo"},
            "recent_decisions": [{"status": "filled"}, {"status": "rejected"}]}
    row = research_brief(book)
    assert row["external_llm_connected"] is False
    assert row["engine"] == "deterministic_rules_no_llm"
    assert row["paper_fills"] == 1
    assert row["rejections"] == 1
    assert row["equity_available"] is False
