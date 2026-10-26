"""Kronos-mini input preparation. Does not load weights or generate forecasts."""

from solana_ai_bot.candles import INTERVALS, CandleSettings, number

MODEL_ID = "NeoQuasar/Kronos-mini"
TOKENIZER_ID = "NeoQuasar/Kronos-Tokenizer-2k"


def prepare_input(history, *, horizon=24):
    """Prepare explicit UTC times and OHLCV/turnover for a future predictor.

    This function checks structural consistency, not authenticity of supplied data.
    A readiness result is never a forecast or a trading signal.
    """
    if type(horizon) is not int or not 1 <= horizon <= 128:
        raise ValueError("Horizon must be 1..128 candles")
    settings = CandleSettings.parse(history["settings"])
    candles = history["candles"]
    if not isinstance(candles, list) or len(candles) != settings.limit:
        raise ValueError("Incomplete model input")
    step = INTERVALS[settings.interval]
    times, values = [], []
    columns = ["open", "high", "low", "close", "volume", "amount"]
    for row in candles:
        at = row["timestamp"]
        if (type(at) is not int or at < 0 or at % step
                or (times and at != times[-1] + step)):
            raise ValueError("Invalid model timestamps")
        numeric = [number(row[key], positive=key in columns[:4]) for key in columns]
        o, high, low, close = numeric[:4]
        if not low <= min(o, close) <= max(o, close) <= high:
            raise ValueError("Invalid model price range")
        times.append(at)
        values.append([float(v) for v in numeric])
    return {"model": MODEL_ID, "tokenizer": TOKENIZER_ID, "columns": columns,
            "values": values, "x_timestamp_utc_seconds": times,
            "y_timestamp_utc_seconds": [times[-1] + step * i for i in range(1, horizon + 1)],
            "pair": settings.pair, "interval": settings.interval,
            "provider": history["provider"], "source": history["source"],
            "forecast_generated": False, "actionable": False}
