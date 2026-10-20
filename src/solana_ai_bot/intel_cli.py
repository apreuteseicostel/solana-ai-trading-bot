"""Runnable read-only observation, quote collection and paper experiment commands."""

import json
import os
import time
from dataclasses import replace
from decimal import Decimal
from html import escape
from pathlib import Path

from .copy_paper import CopyConfig, CopyPaper
from .helius_watch import HeliusWatcher, normalize
from .intel_http import JsonTransport, ProviderError
from .intel_models import SOL, USDC, Quote, WalletEvent, address
from .intel_store import IntelStore
from .jupiter_quotes import JupiterQuotes


def add_commands(commands):
    intel = commands.add_parser(
        "intel", help="Wallet intelligence: read-only data and paper experiments"
    )
    sub = intel.add_subparsers(dest="intel_command", required=True)
    for name in (
        "wallet-sync",
        "wallet-replay",
        "quote",
        "paper-follow",
        "paper-replay",
        "report",
        "demo",
        "watch-paper",
    ):
        cmd = sub.add_parser(name)
        cmd.add_argument("--db", type=Path, required=True)
        if name in {"wallet-sync", "paper-follow", "watch-paper"}:
            cmd.add_argument("--wallet", action="append", type=address, required=True)
            cmd.add_argument("--max-requests", type=int, default=100)
        if name in {"wallet-sync", "watch-paper"}:
            cmd.add_argument("--max-pages", type=int, default=3)
            cmd.add_argument("--rounds", type=int, default=1)
            cmd.add_argument("--interval", type=int, default=15)
        if name in {"wallet-replay", "paper-replay"}:
            cmd.add_argument("source", type=Path)
        if name == "quote":
            cmd.add_argument("--input-mint", type=address, required=True)
            cmd.add_argument("--output-mint", type=address, required=True)
            cmd.add_argument("--amount-raw", type=int, required=True)
        if name in {"paper-follow", "paper-replay", "report", "demo", "watch-paper"}:
            cmd.add_argument("--run-id", default="default")
        if name in {"paper-follow", "paper-replay", "watch-paper"}:
            cmd.add_argument("--config", type=Path)
        if name in {"report", "demo", "watch-paper"}:
            cmd.add_argument("--html", type=Path)


def _lines(path, max_lines=10000):
    with path.open(encoding="utf-8") as stream:
        for index in range(max_lines + 1):
            line = stream.readline(262145)
            if not line:
                return
            if index == max_lines or len(line) > 262144:
                raise ValueError("Replay input exceeded limits")
            data = json.loads(line)
            if not isinstance(data, dict):
                raise TypeError("Each replay row must be an object")
            yield data


def _quote(data):
    return Quote(**{**data, "price_impact_pct": Decimal(str(data["price_impact_pct"]))})


def _config(path):
    if path is None:
        return None
    if path.stat().st_size > 16384:
        raise ValueError("Configuration exceeded size limit")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("Configuration must be an object")
    return CopyConfig(**data)


def replay_paper(path, engine):
    for row in _lines(path):
        if row.get("kind") == "mark":
            quote = replace(_quote(row["quote"]), source="user_supplied_replay")
            engine.mark(row["position_key"], quote, now=row["now"])
        else:
            event = WalletEvent(**{**row["event"], "source": "user_supplied_replay"})
            engine.store.add_event(event)
            quote = (
                replace(_quote(row["quote"]), source="user_supplied_replay")
                if row.get("quote")
                else None
            )
            engine.process(event, quote, now=row["now"])


def follow(engine, wallets, provider, *, clock=None, limit=1000):
    """One bounded forward-paper pass; historical fills are never reconstructed."""
    clock = clock or time.time
    wallets = set(wallets)
    if any(engine.store.backfill(wallet) for wallet in wallets):
        return 0
    processed = 0
    for key, position in engine.state()["positions"].items():
        try:
            quote = provider.quote(
                position["mint"], USDC, position["quantity_raw"], now=int(clock())
            )
            engine.mark(key, quote, now=int(clock()))
        except ProviderError:
            # Missing marks remain visibly unknown and block new exposure.
            continue
    for event in engine.store.pending(engine.run_id, limit=limit, wallets=wallets):
        if event.wallet not in wallets or event.source != "helius_parsed_events":
            continue
        now = int(clock())
        if now < event.observed_at + engine.config.min_copy_delay_seconds:
            continue  # Keep pending until the declared observation delay elapsed.
        request = engine.request_for(event)
        quote, failure = None, None
        if request and now - event.block_time <= engine.config.max_signal_age_seconds:
            try:
                quote = provider.quote(*request, now=int(clock()))
            except ProviderError:
                failure = "quote_provider_unavailable"
        engine.process(event, quote, now=int(clock()), failure=failure)
        processed += 1
    return processed


def write_dashboard(path, report):
    """Escaped, self-contained snapshot. No keys, remote resources or control endpoints."""

    def money(value):
        return "Unknown" if value is None else f"{value / 1_000_000:,.4f} USDC"

    cards = {
        "Paper cash": money(report["state"]["cash_raw"]),
        "Realized paper P&L": money(report["state"]["realized_pnl_raw"]),
        "Unrealized paper P&L": money(report["unrealized_pnl_raw"]),
        "Liquidation equity": money(report["equity_raw"]),
        "Estimated network costs": money(report["state"]["estimated_network_cost_raw"]),
        "Max observed drawdown": f"{report['state']['max_drawdown_bps'] / 100:.2f}%",
    }
    card_html = "".join(
        f"<article><small>{escape(label)}</small><strong>{escape(value)}</strong></article>"
        for label, value in cards.items()
    )
    rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{escape(str(item.get(key, '')))}</td>"
            for key in ("signature", "source", "status", "side", "reason")
        )
        + "</tr>"
        for item in report["recent_decisions"]
    )
    content = (
        """<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <title>Solana Intelligence · Paper Research</title><style>
    body{background:#0b1220;color:#e4eaf3;font:16px system-ui;margin:0;padding:32px}
    main{max-width:1200px;margin:auto}h1{font-size:30px}p,small{color:#a9b9ce}
    .badge{color:#59ddb0;border:1px solid #306b59;padding:8px 14px;border-radius:20px;display:inline-block}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin:30px 0}
    article{padding:22px;background:#142135;border:1px solid #273a54;border-radius:12px}
    strong{display:block;font-size:23px;margin-top:12px}.scroll{overflow:auto}
    table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:12px;border-bottom:1px solid #273a54}
    td:first-child{max-width:170px;overflow-wrap:anywhere}footer{margin-top:25px;color:#a9b9ce}</style>
    <main><span class="badge">PAPER ONLY · NO LIVE EXECUTION</span><h1>Solana Market Intelligence</h1>
    <p>Recorded observations → quote checks → risk limits → simulated fills</p>
    """
        + '<section class="cards">'
        + card_html
        + "</section>"
        + (
            "<p>Run: "
            + escape(report["run_id"])
            + " · "
            + escape(report["equity_status"])
            + " · Halted: "
            + str(report["state"]["halted"])
            + "</p>"
            '<div class="scroll"><table><thead><tr><th>Signature</th><th>Data source</th><th>Status</th>'
            "<th>Side</th><th>Reason</th></tr></thead><tbody>"
            + rows
            + "</tbody></table></div>"
            "<footer>Static snapshot. Demo/replay data are unverified. P&L is simulated in USDC, "
            "not realized wallet profit. Network costs are estimates; API subscription costs are not included. "
            "Regenerate the report to refresh it.</footer></main></html>"
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def demo(engine):
    """Deterministic synthetic buy/transfer/sell, with all sources labelled demo."""
    wallet = "11111111111111111111111111111111"
    origin = 1_800_000_000
    first = WalletEvent(
        wallet,
        "demo-buy",
        1,
        origin,
        origin + 1,
        "swap",
        "synthetic_fixture",
        USDC,
        SOL,
        25_000_000,
        250_000_000,
        source="synthetic_demo",
    )
    transfer = WalletEvent(
        wallet,
        "demo-transfer",
        2,
        origin + 5,
        origin + 6,
        "transfer",
        "not_a_swap",
        source="synthetic_demo",
    )
    last = WalletEvent(
        wallet,
        "demo-sell",
        3,
        origin + 10,
        origin + 11,
        "swap",
        "synthetic_fixture",
        SOL,
        USDC,
        250_000_000,
        27_000_000,
        source="synthetic_demo",
    )
    buy = Quote(
        USDC,
        SOL,
        engine.config.trade_size_raw,
        250_000_000,
        248_750_000,
        Decimal("0.1"),
        origin + 3,
        1,
        "synthetic_demo",
    )
    sell = Quote(
        SOL,
        USDC,
        248_750_000,
        27_000_000,
        26_865_000,
        Decimal("0.1"),
        origin + 13,
        3,
        "synthetic_demo",
    )
    for event, quote, at in (
        (first, buy, origin + 3),
        (transfer, None, origin + 8),
        (last, sell, origin + 13),
    ):
        engine.store.add_event(event)
        engine.process(event, quote, now=at)
    return origin + 13


def run(args):
    try:
        command = args.intel_command
        if (
            command in {"wallet-replay", "paper-replay"}
            and args.source.resolve() == args.db.resolve()
        ):
            raise ValueError("Replay source and database must differ")
        with IntelStore(args.db) as store:
            if command == "wallet-replay":
                count = 0
                for row in _lines(args.source):
                    event = normalize(row["item"], row["wallet"], row["observed_at"])
                    count += store.add_event(
                        replace(event, source="user_supplied_replay")
                    )
                result = {"new_events": count, "source": "user_supplied_replay"}
            elif command == "wallet-sync":
                if not 1 <= args.rounds <= 60 or not 5 <= args.interval <= 60:
                    raise ValueError("rounds must be 1..60 and interval 5..60 seconds")
                transport = JsonTransport(
                    max_requests=args.max_requests, on_request=store.record_request
                )
                watcher = HeliusWatcher(os.getenv("HELIUS_API_KEY"), transport)
                results = []
                for index in range(args.rounds):
                    for wallet in dict.fromkeys(args.wallet):
                        results.append(
                            {
                                "wallet": wallet,
                                **watcher.sync(
                                    wallet,
                                    store,
                                    observed_at=int(time.time()),
                                    max_pages=args.max_pages,
                                ),
                            }
                        )
                    if index + 1 < args.rounds:
                        time.sleep(args.interval)
                result = {"sync": results, "provider_requests": transport.requests}
            elif command == "quote":
                provider = JupiterQuotes(
                    os.getenv("JUPITER_API_KEY"),
                    JsonTransport(max_requests=3, on_request=store.record_request),
                )
                quote = provider.quote(
                    args.input_mint,
                    args.output_mint,
                    args.amount_raw,
                    now=int(time.time()),
                )
                store.add_quote(quote)
                result = quote.record()
            else:
                if command == "report" and store.run(args.run_id) is None:
                    raise ValueError("Paper experiment not found")
                config = _config(args.config) if hasattr(args, "config") else None
                engine = CopyPaper(store, args.run_id, config)
                now = int(time.time())
                if command == "watch-paper":
                    if not 1 <= args.rounds <= 60 or not 5 <= args.interval <= 60:
                        raise ValueError(
                            "rounds must be 1..60 and interval 5..60 seconds"
                        )
                    transport = JsonTransport(
                        max_requests=args.max_requests, on_request=store.record_request
                    )
                    watcher = HeliusWatcher(os.getenv("HELIUS_API_KEY"), transport)
                    provider = JupiterQuotes(os.getenv("JUPITER_API_KEY"), transport)
                    for index in range(args.rounds):
                        complete = True
                        for wallet in dict.fromkeys(args.wallet):
                            sync = watcher.sync(
                                wallet,
                                store,
                                observed_at=int(time.time()),
                                max_pages=args.max_pages,
                            )
                            complete = complete and sync["complete"]
                        if complete:
                            follow(engine, args.wallet, provider)
                        if index + 1 < args.rounds:
                            time.sleep(args.interval)
                    now = int(time.time())
                elif command == "paper-replay":
                    replay_paper(args.source, engine)
                    now = engine.state()["last_time"]
                elif command == "paper-follow":
                    provider = JupiterQuotes(
                        os.getenv("JUPITER_API_KEY"),
                        JsonTransport(
                            max_requests=args.max_requests,
                            on_request=store.record_request,
                        ),
                    )
                    follow(engine, args.wallet, provider)
                    now = int(time.time())
                elif command == "demo":
                    now = demo(engine)
                result = engine.report(now=now)
                result["provider_usage"] = store.provider_usage()
                if getattr(args, "html", None):
                    if args.html.resolve() == args.db.resolve():
                        raise ValueError("HTML destination must differ from database")
                    write_dashboard(args.html, result)
            print(
                json.dumps(
                    {"read_only": True, "live_execution_available": False, **result},
                    indent=2,
                )
            )
            return 0
    except (ProviderError, ValueError, TypeError, KeyError, OSError):
        # Neither provider payloads nor exception strings can leak credentials.
        print(
            json.dumps(
                {
                    "error": "Intelligence command failed: check configuration, input schema, "
                    "provider credentials/access and documented limits. No live orders are supported."
                }
            )
        )
        return 2
