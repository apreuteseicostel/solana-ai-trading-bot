"""Bounded public OHLCV research data, independent of paper execution."""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from .intel_http import JsonTransport, ProviderError

PROVIDERS = {
    "binance_public": "https://data-api.binance.vision/api/v3/klines",
    "binance_rest": "https://api.binance.com/api/v3/klines",
}
INTERVALS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
PAIRS = ("BTC/USDT", "ETH/USDT", "SOL/USDT")


@dataclass(frozen=True)
class CandleSettings:
    primary: str = "binance_public"
    backup: str = "none"
    pair: str = "BTC/USDT"
    interval: str = "1h"
    limit: int = 128

    def __post_init__(self):
        if (self.primary not in PROVIDERS or self.backup not in (*PROVIDERS, "none")
                or self.backup == self.primary or self.pair not in PAIRS
                or self.interval not in INTERVALS or type(self.limit) is not int
                or not 32 <= self.limit <= 512):
            raise ValueError("Unsupported candle settings")

    @classmethod
    def parse(cls, payload):
        if not isinstance(payload, dict) or set(payload) - set(cls.__dataclass_fields__):
            raise ValueError("Unsupported settings fields")
        return cls(**payload)


def catalogue():
    return {
        "defaults": asdict(CandleSettings()),
        "providers": [
            {"id": "binance_public", "label": "Binance public market data", "exchange": "Binance spot"},
            {"id": "binance_rest", "label": "Binance REST (same exchange)", "exchange": "Binance spot"},
        ],
        "pairs": PAIRS, "intervals": list(INTERVALS),
        "other_sources": "Helius wallet events and Jupiter quotes are not OHLCV histories.",
        "kronos": {"model": "NeoQuasar/Kronos-mini",
                   "tokenizer": "NeoQuasar/Kronos-Tokenizer-2k",
                   "status": "not_loaded", "forecasts_available": False},
        "execution": "research_only",
    }


def settings_preview(payload):
    return {"settings": asdict(CandleSettings.parse(payload)), "provider_calls": 0,
            "saved_on_server": False, "orders_submitted": False}


def number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError("Invalid candle value")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid candle value") from None
    if not result.is_finite() or result < 0 or result > Decimal("1e30"):
        raise ValueError("Invalid candle value")
    if positive and result == 0:
        raise ValueError("Non-positive price")
    return result


def normalise(raw, settings, *, now):
    """Reject bad history; remove only the still-open final bar, never fill gaps."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= settings.limit + 1:
        raise ValueError("Invalid candle response size")
    step = INTERVALS[settings.interval] * 1000
    now_ms = int(now * 1000)
    candles = []
    previous = None
    for index, row in enumerate(raw):
        if not isinstance(row, list) or len(row) != 12:
            raise ValueError("Invalid candle row")
        start, end = row[0], row[6]
        if (type(start) is not int or type(end) is not int or start < 0
                or start % step or end != start + step - 1 or start > now_ms):
            raise ValueError("Invalid candle timestamps")
        if previous is not None and start != previous + step:
            raise ValueError("Duplicate, unordered or missing candles")
        previous = start
        o, h, low, c = [number(v, positive=True) for v in row[1:5]]
        volume, amount = number(row[5]), number(row[7])
        if not low <= min(o, c) <= max(o, c) <= h:
            raise ValueError("Invalid OHLC range")
        if end >= now_ms:
            if index != len(raw) - 1:
                raise ValueError("Open candle inside history")
            continue
        candles.append({"timestamp": start // 1000, "open": str(o), "high": str(h),
                        "low": str(low), "close": str(c), "volume": str(volume),
                        "amount": str(amount)})
    candles = candles[-settings.limit:]
    if len(candles) != settings.limit:
        raise ValueError("Insufficient closed candles")
    # Latest complete UTC bar must be present, including at exact boundaries.
    latest_expected = (now_ms // step - 1) * step
    if candles[-1]["timestamp"] * 1000 != latest_expected:
        raise ValueError("Stale candle history")
    return candles


def fetch_candles(settings, *, now, transport=None):
    """At most one request per configured endpoint; no mixed-source series."""
    transport = transport or JsonTransport(max_requests=2, retries=0, timeout=3)
    attempts = []
    for provider in (settings.primary, settings.backup):
        if provider == "none":
            continue
        query = urlencode({"symbol": settings.pair.replace("/", ""),
                           "interval": settings.interval, "limit": settings.limit + 1,
                           "endTime": int(now * 1000)})
        try:
            raw = transport.request("GET", PROVIDERS[provider] + "?" + query)
            candles = normalise(raw, settings, now=now)
        except (ProviderError, ValueError, TypeError, OverflowError):
            attempts.append({"provider": provider, "status": "unavailable_or_invalid"})
            continue
        attempts.append({"provider": provider, "status": "accepted"})
        return {"settings": asdict(settings), "provider": provider, "exchange": "Binance spot",
                "source": "public_provider_response", "observed_at": now,
                "fallback_used": provider != settings.primary, "attempts": attempts,
                "candles": candles, "closed_only": True, "orders_submitted": False,
                "kronos_status": "input_ready_model_not_loaded"}
    raise ProviderError("No configured source returned a complete, fresh candle history")
