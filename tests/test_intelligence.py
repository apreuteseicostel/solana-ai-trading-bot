"""Behavioral regressions for provider boundaries, copy accounting and restart safety."""

import json
from dataclasses import asdict, replace
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

from solana_ai_bot.cli import main
from solana_ai_bot.copy_paper import CopyConfig, CopyPaper, position_key
from solana_ai_bot.helius_watch import HeliusWatcher, normalize
from solana_ai_bot.intel_cli import follow, write_dashboard
from solana_ai_bot.intel_http import ProviderError
from solana_ai_bot.intel_models import SOL, USDC, Quote, WalletEvent, address
from solana_ai_bot.intel_store import IntelStore
from solana_ai_bot.jupiter_quotes import JupiterQuotes

WALLET = "11111111111111111111111111111111"


def observation(signature="buy", *, sell=False, at=100):
    return WalletEvent(
        WALLET,
        signature,
        1,
        at,
        at + 1,
        "swap",
        "verified_two_token_legs",
        SOL if sell else USDC,
        USDC if sell else SOL,
        100 if sell else 25_000_000,
        30_000_000 if sell else 100,
    )


def quote(*, sell=False, at=103, amount=None, out=None, minimum=None):
    out = out if out is not None else (30_000_000 if sell else 100)
    return Quote(
        SOL if sell else USDC,
        USDC if sell else SOL,
        amount if amount is not None else (99 if sell else 25_000_000),
        out,
        minimum if minimum is not None else out * 99 // 100,
        Decimal("0.1"),
        at,
        1,
    )


def parsed(signature="sig", *, kind="swap", at=100):
    return {
        "signature": signature,
        "parserStatus": "OK",
        "parsed": {
            "slot": 1,
            "blockTime": at,
            "fee": 5000,
            "feePayer": WALLET,
            "transactionStatus": "OK",
            "summary": {
                "type": kind,
                "parsedData": {
                    "input_mint": USDC,
                    "output_mint": SOL,
                    "in_amount": "25000000",
                    "actual_out_amount": "100",
                },
            },
            "tokenTransfers": [
                {
                    "fromUserAccount": WALLET,
                    "toUserAccount": "pool",
                    "mint": USDC,
                    "rawTokenAmount": 25_000_000,
                },
                {
                    "fromUserAccount": "pool",
                    "toUserAccount": WALLET,
                    "mint": SOL,
                    "rawTokenAmount": 100,
                },
            ],
        },
    }


class Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def store(tmp_path):
    with IntelStore(tmp_path / "research.sqlite") as database:
        yield database


def test_only_verified_swaps_generate_signals():
    event = normalize(parsed(), WALLET, 101)
    assert event.kind == "swap" and event.input_raw == 25_000_000
    assert event.network_fee_lamports == 5000
    assert normalize(parsed(kind="transfer"), WALLET, 101).kind == "transfer"
    item = parsed()
    item["parsed"]["feePayer"] = SOL
    assert normalize(item, WALLET, 101).kind == "ignored"


@pytest.mark.parametrize(
    "change", ["failed", "parser", "native", "extra_token", "float", "missing_summary"]
)
def test_ambiguous_or_failed_transactions_never_become_swaps(change):
    item = parsed()
    if change == "failed":
        item["parsed"]["transactionStatus"] = "FAILED"
    elif change == "parser":
        item["parserStatus"] = "NOT_FOUND"
    elif change == "native":
        item["parsed"]["tokenTransfers"].pop()
    elif change == "extra_token":
        item["parsed"]["tokenTransfers"].append(
            {
                "fromUserAccount": WALLET,
                "toUserAccount": "pool",
                "mint": WALLET,
                "rawTokenAmount": 1,
            }
        )
    elif change == "float":
        item["parsed"]["tokenTransfers"][0]["rawTokenAmount"] = 25_000_000.0
    else:
        item["parsed"]["summary"]["parsedData"] = None
    assert normalize(item, WALLET, 101).kind == "ignored"


def test_pagination_resumes_after_restart_without_skipping(store):
    provider = Transport(
        {"data": [parsed("new", at=110)], "paginationToken": "cursor-1"}
    )
    first = HeliusWatcher("not-a-real-key", provider).sync(
        WALLET, store, observed_at=120, max_pages=1
    )
    assert first["resume_pending"] and store.checkpoint(WALLET) is None
    provider = Transport({"data": [parsed("old", at=100)], "paginationToken": None})
    result = HeliusWatcher("not-a-real-key", provider).sync(
        WALLET, store, observed_at=130
    )
    assert provider.calls[0][2]["body"]["paginationToken"] == "cursor-1"
    assert result["complete"] and store.checkpoint(WALLET) == "new"
    assert store.backfill(WALLET) is None
    assert [e.signature for e in store.events()] == ["old", "new"]


def test_partial_provider_failure_does_not_advance_history(store):
    provider = Transport(
        {"data": [parsed()], "paginationToken": "cursor"}, ProviderError("offline")
    )
    with pytest.raises(ProviderError):
        HeliusWatcher("not-a-real-key", provider).sync(WALLET, store, observed_at=101)
    assert store.checkpoint(WALLET) is None
    assert store.backfill(WALLET)["pagination_token"] == "cursor"
    assert len(list(store.events())) == 1


def test_repeated_cursor_and_duplicate_observation(store):
    provider = Transport(*[{"data": [parsed()], "paginationToken": "same"}] * 2)
    with pytest.raises(ProviderError, match="pagination"):
        HeliusWatcher("not-a-real-key", provider).sync(WALLET, store, observed_at=101)
    assert len(list(store.events())) == 1
    assert store.checkpoint(WALLET) is None


def test_jupiter_v2_has_no_taker_or_execute_and_preserves_fee_units():
    data = {
        "inputMint": USDC,
        "outputMint": SOL,
        "inAmount": "25000000",
        "outAmount": "100",
        "otherAmountThreshold": "99",
        "priceImpact": -0.4,
        "swapMode": "ExactIn",
        "transaction": None,
        "feeBps": 5,
        "platformFee": {"amount": "12500", "feeMint": USDC},
    }
    transport = Transport(data)
    result = JupiterQuotes("not-a-real-key", transport).quote(
        USDC, SOL, 25_000_000, now=103
    )
    assert result.price_impact_pct == Decimal("-0.4")
    assert result.platform_fee_raw == 12500
    method, url, kwargs = transport.calls[0]
    assert method == "GET" and urlsplit(url).path == "/swap/v2/order"
    assert "taker" not in parse_qs(urlsplit(url).query)
    assert kwargs["headers"] == {"x-api-key": "not-a-real-key"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("priceImpact", "NaN"),
        ("outAmount", "0"),
        ("inAmount", "24"),
        ("inputMint", SOL),
        ("transaction", "unexpected"),
        ("swapMode", "ExactOut"),
        ("otherAmountThreshold", "1"),
        ("platformFee", [1]),
    ],
)
def test_jupiter_rejects_malformed_quotes(field, value):
    data = {
        "inputMint": USDC,
        "outputMint": SOL,
        "inAmount": "25000000",
        "outAmount": "100",
        "otherAmountThreshold": "99",
        "priceImpact": "0.1",
        "swapMode": "ExactIn",
    }
    data[field] = value
    with pytest.raises(ProviderError):
        JupiterQuotes("not-a-real-key", Transport(data)).quote(
            USDC, SOL, 25_000_000, now=103
        )


def test_round_trip_accounting_restart_and_idempotency(store):
    engine = CopyPaper(store)
    event = observation()
    fill = engine.process(event, quote(), now=103)
    assert fill["status"] == "filled"
    assert engine.state()["cash_raw"] == 974_990_000
    assert engine.report(now=103)["equity_raw"] is None
    restarted = CopyPaper(store)
    assert restarted.process(event, quote(), now=104) == fill
    sell = observation("sell", sell=True, at=110)
    result = restarted.process(sell, quote(sell=True, at=113), now=113)
    assert result["status"] == "filled"
    assert result["realized_pnl_raw"] == 4_680_000
    assert restarted.state()["cash_raw"] == 1_004_680_000
    assert restarted.state()["positions"] == {}
    assert restarted.state()["estimated_network_cost_raw"] == 20_000


@pytest.mark.parametrize(
    "problem,reason",
    [
        ("old_signal", "stale_signal"),
        ("early", "copy_delay_not_elapsed"),
        ("future_quote", "quote_predates_copy_or_is_from_future"),
        ("past_quote", "quote_predates_copy_or_is_from_future"),
        ("stale_quote", "stale_quote"),
        ("impact", "price_impact_limit"),
        ("amount", "quote_does_not_match_order"),
        ("none", "missing_quote"),
    ],
)
def test_rejected_signal_cannot_change_balances(store, problem, reason):
    engine = CopyPaper(store)
    event, q, now = observation(), quote(), 103
    if problem == "old_signal":
        now = 300
    elif problem == "early":
        now = 102
    elif problem == "future_quote":
        q = replace(q, fetched_at=104)
    elif problem == "past_quote":
        q = replace(q, fetched_at=102)
    elif problem == "stale_quote":
        now = 120
    elif problem == "impact":
        q = replace(q, price_impact_pct=Decimal("1.01"))
    elif problem == "amount":
        q = replace(q, input_raw=1)
    else:
        q = None
    assert engine.process(event, q, now=now)["reason"] == reason
    assert engine.state()["cash_raw"] == engine.config.starting_cash_raw
    assert engine.state()["positions"] == {}


def test_drawdown_halt_blocks_buys_but_allows_exits(store):
    engine = CopyPaper(store, config=CopyConfig(max_drawdown_bps=100, max_positions=1))
    event = observation()
    engine.process(event, quote(), now=103)
    engine.mark(
        position_key(event, SOL), quote(sell=True, at=104, out=10_000_000), now=104
    )
    assert engine.state()["halted"]
    assert CopyPaper(store).state()["halted"]
    assert (
        engine.process(observation("buy-again", at=103), quote(at=106), now=106)[
            "reason"
        ]
        == "drawdown_halt"
    )
    result = engine.process(
        observation("sell", sell=True, at=107),
        quote(sell=True, at=110, out=10_000_000),
        now=110,
    )
    assert result["status"] == "filled"


def test_daily_loss_limit_and_utc_reset(store):
    engine = CopyPaper(store, config=CopyConfig(max_daily_loss_raw=1_000_000))
    engine.process(observation(), quote(), now=103)
    engine.process(
        observation("sell", sell=True, at=110),
        quote(sell=True, at=113, out=20_000_000),
        now=113,
    )
    assert (
        engine.process(observation("same-day", at=120), quote(at=123), now=123)[
            "reason"
        ]
        == "daily_loss_limit"
    )
    assert (
        engine.process(observation("tomorrow", at=86500), quote(at=86503), now=86503)[
            "status"
        ]
        == "filled"
    )


def test_fresh_marks_required_and_stale_equity_never_fabricated(store):
    engine = CopyPaper(store)
    event = observation()
    engine.process(event, quote(), now=103)
    assert (
        engine.process(observation("second", at=104), quote(at=107), now=107)["reason"]
        == "fresh_liquidation_marks_required"
    )
    engine.mark(position_key(event, SOL), quote(sell=True, at=108), now=108)
    assert engine.report(now=108)["equity_raw"] == 1_004_680_000
    assert engine.report(now=124)["equity_raw"] is None
    assert (
        engine.process(observation("third", at=124), quote(at=127), now=127)["reason"]
        == "fresh_liquidation_marks_required"
    )


@pytest.mark.parametrize(
    "config,reason",
    [
        (CopyConfig(starting_cash_raw=1), "insufficient_paper_cash"),
        (CopyConfig(max_position_cost_raw=1), "position_exposure_limit"),
        (CopyConfig(max_total_cost_raw=1), "total_exposure_limit"),
    ],
)
def test_capital_limits(store, config, reason):
    engine = CopyPaper(store, config=config)
    assert engine.process(observation(), quote(), now=103)["reason"] == reason


def test_immutable_config_and_transaction_rollback(store):
    CopyPaper(store)
    with pytest.raises(ValueError, match="immutable"):
        CopyPaper(store, config=CopyConfig(trade_size_raw=1))
    with pytest.raises(RuntimeError), store.transaction():
        store.add_event(observation())
        raise RuntimeError("rollback")
    assert list(store.events()) == []


def test_forward_pass_skips_replay_and_never_quotes_old_events(store):
    old = observation(at=1)
    store.add_event(old)
    store.add_event(replace(observation("fixture"), source="synthetic_demo"))
    engine = CopyPaper(store)

    class NoCalls:
        def quote(self, *args, **kwargs):
            raise AssertionError("No quote needed")

    assert follow(engine, [WALLET], NoCalls(), clock=lambda: 300) == 1
    assert store.decision("default", old)["reason"] == "stale_signal"
    assert engine.state()["cash_raw"] == 1_000_000_000


def test_delay_keeps_signal_pending_and_provider_error_is_journalled(store):
    event = observation()
    store.add_event(event)
    engine = CopyPaper(store)

    class Offline:
        def quote(self, *args, **kwargs):
            raise ProviderError("offline")

    assert follow(engine, [WALLET], Offline(), clock=lambda: 102) == 0
    assert store.decision("default", event) is None
    assert follow(engine, [WALLET], Offline(), clock=lambda: 103) == 1
    assert store.decision("default", event)["reason"] == "quote_provider_unavailable"


def test_demo_cli_report_and_escape(tmp_path, capsys):
    db, html = tmp_path / "demo.sqlite", tmp_path / "dashboard.html"
    args = ["intel", "demo", "--db", str(db), "--html", str(html), "--run-id", "demo"]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["state"]["realized_pnl_raw"] == 1_845_000
    assert not report["live_execution_available"]
    assert {d["source"] for d in report["recent_decisions"]} == {"synthetic_demo"}
    assert "PAPER ONLY" in html.read_text()
    assert main(args) == 0
    again = json.loads(capsys.readouterr().out)
    assert again["state"] == report["state"]
    report["run_id"] = "<script>alert(1)</script>"
    write_dashboard(html, report)
    assert "<script>" not in html.read_text()


def test_missing_credentials_fail_without_network(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HELIUS_API_KEY", raising=False)
    assert (
        main(["intel", "wallet-sync", "--db", str(tmp_path / "db"), "--wallet", WALLET])
        == 2
    )
    assert "error" in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    "value", ["", "x" * 44, "1" * 31, SOL + "1", "https://example.com"]
)
def test_public_addresses_are_validated(value):
    with pytest.raises(ValueError):
        address(value)


def test_integer_config_and_exact_arithmetic(store):
    with pytest.raises(TypeError):
        CopyConfig(trade_size_raw="25")
    with pytest.raises(TypeError):
        CopyConfig(max_positions=True)
    assert asdict(CopyConfig())["estimated_network_fee_raw"] > 0


def test_source_isolation_prevents_fixture_profit_entering_forward_book(store):
    engine = CopyPaper(store)
    engine.process(observation(), quote(), now=103)
    event = replace(
        observation("fake-sell", sell=True, at=110), source="user_supplied_replay"
    )
    result = engine.process(
        event, replace(quote(sell=True, at=113), source="user_supplied_replay"), now=113
    )
    assert result["reason"] == "mixed_data_sources_use_separate_run"
    assert engine.state()["realized_pnl_raw"] == 0
    assert engine.state()["positions"]


def test_entry_impact_cap_does_not_trap_an_exit(store):
    engine = CopyPaper(store)
    engine.process(observation(), quote(), now=103)
    result = engine.process(
        observation("sell", sell=True, at=110),
        replace(quote(sell=True, at=113), price_impact_pct=Decimal(5)),
        now=113,
    )
    assert result["status"] == "filled"


def test_failed_history_snapshot_is_not_used_for_forward_fills(store):
    store.add_event(observation())
    store.save_backfill(WALLET, {"pagination_token": "next"})
    assert follow(CopyPaper(store), [WALLET], object(), clock=lambda: 103) == 0


def test_missing_report_never_invents_starting_capital(tmp_path, capsys):
    assert (
        main(["intel", "report", "--db", str(tmp_path / "none"), "--run-id", "missing"])
        == 2
    )
    assert "cash_raw" not in capsys.readouterr().out


def test_real_restart_keeps_first_observation_time(tmp_path):
    path = tmp_path / "persistent.sqlite"
    with IntelStore(path) as db:
        db.add_event(observation())
        CopyPaper(db).process(observation(), quote(), now=103)
    with IntelStore(path) as db:
        assert db.add_event(replace(observation(), observed_at=200)) == 0
        assert next(db.events()).observed_at == 101
        engine = CopyPaper(db)
        assert engine.state()["cash_raw"] == 974_990_000
        assert engine.process(observation(), quote(), now=300)["at"] == 103


def test_forward_quote_provider_integration(store):
    event = normalize(parsed(), WALLET, 101)
    store.add_event(event)
    provider = JupiterQuotes(
        "not-a-real-key",
        Transport(
            {
                "inputMint": USDC,
                "outputMint": SOL,
                "inAmount": "25000000",
                "outAmount": "100",
                "otherAmountThreshold": "99",
                "priceImpact": "0.1",
                "swapMode": "ExactIn",
            }
        ),
    )
    engine = CopyPaper(store)
    assert follow(engine, [WALLET], provider, clock=lambda: 103) == 1
    assert engine.store.decision("default", event)["status"] == "filled"
    assert engine.state()["dataset_mode"] == "forward_observations"


def test_paper_replay_cli_forces_unverified_provenance(tmp_path, capsys):
    source = tmp_path / "events.jsonl"
    source.write_text(
        json.dumps(
            {"event": observation().record(), "quote": quote().record(), "now": 103}
        )
    )
    assert (
        main(
            [
                "intel",
                "paper-replay",
                str(source),
                "--db",
                str(tmp_path / "replay.sqlite"),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    decision = report["recent_decisions"][0]
    assert decision["source"] == decision["quote"]["source"] == "user_supplied_replay"


def test_combined_watch_paper_loop_observes_before_copying(
    tmp_path, monkeypatch, capsys
):
    from solana_ai_bot import intel_cli

    clock = {"now": 101}
    calls = []

    class Watcher:
        def __init__(self, key, transport):
            pass

        def sync(self, wallet, store, **kwargs):
            store.add_event(observation())
            return {"complete": True}

    class Quotes:
        def __init__(self, key, transport):
            pass

        def quote(self, *args, now):
            calls.append(now)
            return quote(at=now)

    monkeypatch.setattr(intel_cli, "HeliusWatcher", Watcher)
    monkeypatch.setattr(intel_cli, "JupiterQuotes", Quotes)
    monkeypatch.setattr(intel_cli.time, "time", lambda: clock["now"])
    monkeypatch.setattr(
        intel_cli.time, "sleep", lambda delay: clock.update(now=clock["now"] + delay)
    )
    assert (
        main(
            [
                "intel",
                "watch-paper",
                "--db",
                str(tmp_path / "combined.sqlite"),
                "--wallet",
                WALLET,
                "--rounds",
                "2",
                "--interval",
                "5",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert calls == [106]
    assert report["recent_decisions"][0]["status"] == "filled"
    assert report["state"]["dataset_mode"] == "forward_observations"
