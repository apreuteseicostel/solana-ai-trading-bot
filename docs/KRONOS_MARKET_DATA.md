# Core-market data and Kronos foundation

This increment builds on PR #16 (which depends on #15). It adds the **Data
sources / Kronos** page to the existing local dashboard, without changing a
paper book or enabling order execution.

## Use

```sh
python -m pip install -e '.[dev]'
python -m solana_ai_bot.dashboard --demo
# http://127.0.0.1:8765/#market
```

Choose primary endpoint, optional backup, pair (BTC/USDT, ETH/USDT, SOL/USDT),
UTC interval (15m, 1h, 4h, 1d), and 32–512 closed candles. Preferences are
validated by the server and saved only in the current browser/local origin.
Saving or restoring preferences makes no outbound request. Click **Fetch public
candles** for one bounded read session. The last 12 bars are displayed; the API
returns the full selected window. This page does not change the existing SMA
fixture, DCA calculator or Solana USDC paper book.

Both implemented providers serve **Binance spot**: the market-data-only endpoint
and the Binance REST endpoint. This is endpoint redundancy on one venue, not
independent price confirmation. Other exchanges require separate tested adapters;
Helius wallet events and Jupiter quotes cannot stand in for OHLCV. USDT is not
converted to or assumed equivalent to USDC. Access may vary by network/region.

## Contracts and boundaries

- `GET /api/market/catalogue`: supported options and honest model status.
- `POST /api/market/settings`: validation only, no server write or provider call.
- `POST /api/market/candles`: explicit public market read, no credentials/signing.
- Existing localhost Host/Origin, JSON type and 16 KiB request limits apply.
- Two fixed HTTPS GET endpoints only; no arbitrary URL, redirects or order API.
- At most two upstream requests, no retries, three-second socket timeout each,
  four-megabyte maximum response. A socket timeout is not a hard wall-clock
  deadline for DNS or an upstream trickling a response; production transport
  still needs an absolute deadline/rate limiter before exposing this service.
- Fetch `limit + 1` bars with an explicit end time; remove only an unfinished
  final bar. Reject malformed/nonfinite OHLCV, invalid high/low, bad time bounds,
  duplicates, gaps, unsorted rows, insufficient history or missing latest closed
  UTC bar. No fabricated fills or prices. No automatic refresh.
- Failover replaces the entire series; never concatenate sources. The returned
  provider, pair, exchange, interval, observed time and attempts remain explicit.
- Public provider responses establish provenance, not independent authenticity
  or profitability. The UI clears a result when starting a new request.

## Kronos preparation

`solana_ai_bot.ai.kronos.prepare_input(history, horizon=24)` prepares validated
numeric open/high/low/close/volume/amount, historical UTC timestamps and strictly
future timestamps for the upstream predictor contract. `amount` is the actual
quote turnover, not close multiplied by base volume. It preserves source identity
and returns `forecast_generated=false` and `actionable=false`.

The intended pair is **NeoQuasar/Kronos-mini** with
**NeoQuasar/Kronos-Tokenizer-2k**. Upstream documents a 2048-token context for mini;
this first data-fetch increment caps history at 512. No weight download, PyTorch
installation, model inference, confidence score or prediction-driven signal is
implemented. Input preparation is a separate Python interface, not a forecast UI.

References checked 26 October 2026:
- https://github.com/shiyu-coder/Kronos (README; predictor inputs/model table)
- https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md

## Agreed direction and next increments

Core research focuses on established liquid assets with history, for trading and
DCA. A separate early-project module must have an **aggregate maximum 1%** of total
portfolio, not 1% per project. It is not implemented/enabled here. These asset
choices do not mean their prices are stable or that capital is protected.

Next: verified live history/cache, pinned optional Kronos-mini inference worker,
walk-forward comparisons against buy-and-hold, DCA and SMA with fees/slippage and
out-of-sample windows. Only then evaluate forecast-conditioned paper strategies,
net take-profit and aggregate allocation limits. Existing no-live-execution
rules remain in force. Hourly automations have not been restarted.

## Validation

198 offline tests passed, including 34 new tests. `python -m ruff check .` and
`node --check src/solana_ai_bot/web/app.js` passed. A bounded live attempt from
the implementation environment returned no valid history; live compatibility
is **unverified**. No model inference or profitability claim is made.

Browser visual QA could not run: Playwright's Chromium executable was absent
and the browser download failed. JS syntax and HTTP endpoint tests passed;
actual desktop/mobile rendering and preference restore need browser acceptance.
