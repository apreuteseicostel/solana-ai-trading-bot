import copy

import pytest
from test_intel_http import Opener
from test_research_suite import local_request

from solana_ai_bot.ai.kronos import prepare_input
from solana_ai_bot.candles import (
    CandleSettings,
    catalogue,
    fetch_candles,
    normalise,
    settings_preview,
)
from solana_ai_bot.intel_http import JsonTransport, ProviderError

NOW = 3600 * 100
SETTINGS = CandleSettings(limit=32)


def bars():
    return [[i * 3600000, "10", "12", "9", "11", "20",
             (i + 1) * 3600000 - 1, "220", 2, "10", "110", "0"]
            for i in range(68, 101)]


class Transport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url):
        self.calls.append((method, url))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_closed_only_and_real_turnover_preserved():
    result = normalise(bars(), SETTINGS, now=NOW)
    assert len(result) == 32
    assert result[-1]["timestamp"] == 99 * 3600
    assert result[-1]["amount"] == "220"
    assert result[-1]["volume"] == "20"


@pytest.mark.parametrize("payload", [
    {"limit": True}, {"limit": 31}, {"limit": 513}, {"limit": 32.0},
    {"primary": "helius"}, {"backup": "binance_public"}, {"pair": "SOL/USDC"},
    {"interval": "1M"}, {"api_key": "do-not-store"}, {"url": "https://example.com"},
    [], None,
])
def test_invalid_settings(payload):
    with pytest.raises((ValueError, TypeError)):
        settings_preview(payload)


@pytest.mark.parametrize("case", [
    "nan", "negative", "bool", "range", "duplicate", "gap", "reverse",
    "future", "stale", "short", "oversized", "shape", "close_time", "alignment",
])
def test_reject_corrupt_history(case):
    raw = bars()
    if case == "nan": raw[0][4] = "NaN"
    if case == "negative": raw[0][5] = "-1"
    if case == "bool": raw[0][4] = True
    if case == "range": raw[0][2] = "8"
    if case == "duplicate": raw[1] = raw[0]
    if case == "gap": del raw[1]
    if case == "reverse": raw.reverse()
    if case == "future": raw[-1][0] += 3600000
    if case == "stale": raw = bars()[:-2]
    if case == "short": raw = raw[:10]
    if case == "oversized": raw = raw * 2
    if case == "shape": raw[0] = raw[0][:8]
    if case == "close_time": raw[0][6] += 1
    if case == "alignment": raw[0][0] += 1
    with pytest.raises((ValueError, TypeError)):
        normalise(raw, SETTINGS, now=NOW)


def test_fallback_discards_primary_whole_series():
    broken = bars()
    broken[0][1] = "NaN"
    transport = Transport([broken, bars()])
    settings = CandleSettings(limit=32, backup="binance_rest")
    result = fetch_candles(settings, now=NOW, transport=transport)
    assert result["provider"] == "binance_rest"
    assert result["fallback_used"] is True
    assert len(transport.calls) == 2
    assert "limit=33" in transport.calls[0][1]
    assert result["attempts"][0]["status"] == "unavailable_or_invalid"
    assert result["orders_submitted"] is False


def test_no_backup_or_unrequested_network_calls():
    transport = Transport([ProviderError("failure")])
    with pytest.raises(ProviderError):
        fetch_candles(SETTINGS, now=NOW, transport=transport)
    assert len(transport.calls) == 1
    assert settings_preview({})["provider_calls"] == 0
    assert catalogue()["kronos"]["forecasts_available"] is False


def test_both_providers_fail_closed():
    transport = Transport([ProviderError("secret"), []])
    with pytest.raises(ProviderError, match="No configured source") as error:
        fetch_candles(CandleSettings(limit=32, backup="binance_rest"),
                      now=NOW, transport=transport)
    assert "secret" not in str(error.value)
    assert len(transport.calls) == 2


def test_kronos_uses_future_timestamps_and_correct_tokenizer():
    history = fetch_candles(SETTINGS, now=NOW, transport=Transport([bars()]))
    prepared = prepare_input(history, horizon=24)
    assert prepared["tokenizer"] == "NeoQuasar/Kronos-Tokenizer-2k"
    assert prepared["x_timestamp_utc_seconds"][-1] == 99 * 3600
    assert prepared["y_timestamp_utc_seconds"][0] == 100 * 3600
    assert prepared["y_timestamp_utc_seconds"][-1] == 123 * 3600
    assert prepared["values"][0] == [10, 12, 9, 11, 20, 220]
    assert prepared["forecast_generated"] is False
    assert prepared["actionable"] is False
    bad = copy.deepcopy(history)
    bad["candles"][0]["close"] = "Infinity"
    with pytest.raises(ValueError):
        prepare_input(bad)
    with pytest.raises(ValueError):
        prepare_input(history, horizon=129)


def test_candle_transport_accepts_only_allowlisted_reads():
    transport = JsonTransport(max_requests=1, retries=0)
    transport.opener = Opener([b"[]"])
    assert transport.request("GET", "https://data-api.binance.vision/api/v3/klines") == []
    for url in ["https://api.binance.com/api/v3/order",
                "https://user:pass@api.binance.com/api/v3/klines"]:
        with pytest.raises(ProviderError):
            transport.request("GET", url)
    assert transport.requests == 1


def test_http_candles_explicit_read_and_origin_guard(tmp_path, monkeypatch):
    path = tmp_path / "no-db.sqlite"
    calls = []

    def fetch(settings, *, now):
        calls.append(settings)
        return {"candles": [], "orders_submitted": False}

    monkeypatch.setattr("solana_ai_bot.dashboard.fetch_candles", fetch)
    headers, result = local_request(path, "/api/market/catalogue", {}, method="GET")
    assert "200" in headers and result["defaults"]["backup"] == "none"
    assert "200" in local_request(path, "/api/market/settings", {})[0]
    assert calls == []
    assert "403" in local_request(path, "/api/market/candles", {}, origin="https://evil.example")[0]
    assert calls == []
    assert "400" in local_request(path, "/api/market/candles", {"limit": 1000})[0]
    headers, result = local_request(path, "/api/market/candles", {})
    assert "200" in headers and result["orders_submitted"] is False
    assert len(calls) == 1
    assert not path.exists()


def test_http_provider_failure_is_generic(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise ProviderError("secret-provider-details")
    monkeypatch.setattr("solana_ai_bot.dashboard.fetch_candles", fail)
    headers, result = local_request(tmp_path / "none", "/api/market/candles", {})
    assert "503" in headers
    assert "secret" not in str(result)
