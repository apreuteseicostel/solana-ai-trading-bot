"""Offline research utilities for the local dashboard: never sign or route orders.

All output is retrospective, illustrative or unverified until backed by verified
market data. No provider calls, private keys, order execution or DB writes.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .backtest import BacktestConfig, PriceTick, run_sma_backtest

MONEY = Decimal("0.01")
BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
TOKEN_PROGRAMS = {
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "spl_token",
    "TokenzQdBNbLqP5VEhdkAS6EPFhgJ6Z4aVZAP9bvf": "token_2022",
}


def _amount(value, *, ceiling="1000000000"):
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise ValueError("Amounts must be decimal strings or integers")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal amount") from exc
    if not number.is_finite() or number < 0 or number > Decimal(ceiling):
        raise ValueError("Amount outside permitted range")
    if number.as_tuple().exponent < -2:
        raise ValueError("Maximum two decimal places")
    return number


def dca_preview(payload):
    """Compute hypothetical allocations from supplied USDC values, never balances.

    'dca' spends only a supplied contribution toward target underweights;
    'rebalance' includes hypothetical sells to target weights.
    Costs, quotes and trade execution are *not* inferred.
    """
    if not isinstance(payload, dict) or set(payload) - {"holdings", "targets", "contribution_usdc", "mode"}:
        raise ValueError("Unexpected planner input")
    holdings = payload.get("holdings")
    targets = payload.get("targets")
    if not isinstance(holdings, dict) or not isinstance(targets, dict):
        raise ValueError("Holdings and targets must be objects")
    if not 1 <= len(holdings) <= 10 or set(holdings) != set(targets):
        raise ValueError("Use 1..10 matching asset names")
    if any(not isinstance(a, str) or not re.fullmatch(r"[A-Z0-9]{2,12}", a)
           for a in holdings):
        raise ValueError("Use uppercase asset symbols, not wallet addresses")
    mode = payload.get("mode", "dca")
    if mode not in ("dca", "rebalance"):
        raise ValueError("Unsupported planner mode")
    current = {asset: _amount(value) for asset, value in holdings.items()}
    weights = {asset: _amount(value, ceiling="100") for asset, value in targets.items()}
    if sum(weights.values()) != 100:
        raise ValueError("Target allocations must total 100%")
    contribution = _amount(payload.get("contribution_usdc", "0"), ceiling="1000000")
    total = sum(current.values())
    post_total = total + contribution
    if post_total <= 0:
        raise ValueError("Portfolio must have a positive total")
    target_values = {asset: post_total * w / 100 for asset, w in weights.items()}
    deficits = {asset: max(Decimal(0), target_values[asset] - current[asset])
                for asset in current}
    total_deficits = sum(deficits.values())
    result = []
    for asset in sorted(current):
        if mode == "rebalance":
            planned = target_values[asset] - current[asset]
        elif total_deficits:
            planned = contribution * deficits[asset] / total_deficits
        else:
            planned = Decimal(0)
        planned = planned.quantize(MONEY, rounding=ROUND_HALF_UP)
        result.append({
            "asset": asset,
            "current_value_usdc": str(current[asset]),
            "target_pct": str(weights[asset]),
            "target_value_usdc": str(target_values[asset].quantize(MONEY)),
            "delta_usdc": str(planned),
            "action": "illustrative_buy" if planned > 0 else
                      "illustrative_sell" if planned < 0 else "none",
        })
    return {
        "mode": mode, "preview_only": True, "orders_submitted": False,
        "input_provenance": "user_supplied_values_not_wallet_balances",
        "unit": "USDC", "current_total_usdc": str(total),
        "contribution_usdc": str(contribution),
        "planned_net_usdc": str(sum(Decimal(row["delta_usdc"]) for row in result)),
        "rows": result,
        "execution_costs_usdc": None,
        "warning": "Indicative plan only; prices, liquidity, taxes, network fees and slippage are unknown.",
    }


DEMO_PRICES = [10, 9, 8, 9, 10, 12, 13, 12, 11, 10, 9, 8,
               9, 11, 12, 11, 9, 8, 10, 12, 14, 13, 12, 11]


def trend_research(dataset_mode):
    """Show an offline SMA demonstration only for an explicitly synthetic book."""
    if dataset_mode != "synthetic_demo":
        return {
            "available": False,
            "mode": "trend_following",
            "reason": "No independently verified tick/price-history series is connected.",
            "data_source": "unavailable",
            "orders_submitted": False,
        }
    config = BacktestConfig(fast_window=3, slow_window=6, starting_cash=1000,
                            position_fraction=0.10, fee_rate=0.001,
                            slippage_rate=0.005)
    ticks = [PriceTick(i, price) for i, price in enumerate(DEMO_PRICES)]
    result = run_sma_backtest(ticks, config)
    fast = sum(DEMO_PRICES[-3:]) / 3
    slow = sum(DEMO_PRICES[-6:]) / 6
    return {
        "available": True, "mode": "trend_following",
        "data_source": "synthetic_demo_fixed_prices",
        "latest_retrospective_trend": "up" if fast > slow else
                                     "down" if fast < slow else "flat",
        "fast_sma": round(fast, 5), "slow_sma": round(slow, 5),
        "estimated_final_equity_usdc": round(result.estimated_liquidation_equity, 2),
        "estimated_net_pnl_usdc": round(result.estimated_net_pnl, 2),
        "max_drawdown_pct": round(result.max_drawdown_pct, 2),
        "closed_paper_trades": len(result.closed_trades),
        "prices_count": len(ticks), "orders_submitted": False,
        "warning": "Synthetic SMA next-tick backtest. Network/priority costs, failed fills and provider data are NOT modelled.",
    }


def research_brief(book):
    """Produce a factual brief, never pretend it is generated by an LLM."""
    decisions = book.get("recent_decisions", [])
    statuses = {
        "paper_fills": sum(d.get("status") == "filled" for d in decisions),
        "rejections": sum(d.get("status") == "rejected" for d in decisions),
    }
    mode = book["state"].get("dataset_mode") or "unknown"
    return {
        "engine": "deterministic_rules_no_llm",
        "external_llm_connected": False,
        "source": mode, "run_id": book["run_id"],
        "recorded_decision_count": len(decisions),
        **statuses,
        "equity_available": book["equity_raw"] is not None,
        "messages": [
            "Observed records are not proof of collector health or trade profitability.",
            "All recorded fills are simulated; no live order routing is available.",
            "A verified market-history source is required before trend conclusions.",
        ],
        "provider_costs_usdc": None,
        "generated_from": "read_only_sqlite_snapshot",
    }


def _valid_mint(address):
    if not isinstance(address, str) or not 32 <= len(address) <= 44:
        return False
    if any(char not in BASE58 for char in address):
        return False
    number = 0
    for char in address:
        number = number * 58 + BASE58.index(char)
    count = len(address) - len(address.lstrip("1"))
    decoded = b"\x00" * count + (number.to_bytes((number.bit_length() + 7) // 8, "big")
                                if number else b"")
    return len(decoded) == 32


def inspect_token(payload):
    """Inspect *unverified user-supplied* jsonParsed getAccountInfo evidence.

    Does NOT fetch RPC data. Missing liquidity and holder concentration remain
    unknown. Unsupported/malformed responses do not produce safety conclusions.
    """
    if not isinstance(payload, dict) or set(payload) - {"mint", "rpc_response"}:
        raise ValueError("Unexpected token inspection input")
    mint = payload.get("mint")
    if not _valid_mint(mint):
        raise ValueError("Token mint must be a valid 32-byte Solana base58 public key")
    result = {
        "mint": mint, "read_only": True, "orders_submitted": False,
        "provenance": "not_verified_no_onchain_request",
        "authority_check": "unknown",
        "mint_authority_active": None, "freeze_authority_active": None,
        "liquidity_depth_usdc": None, "top_holders_pct": None,
        "token_program": None,
        "warnings": ["No verified live RPC query was performed.",
                     "Liquidity depth and holder concentration remain unknown."],
    }
    rpc = payload.get("rpc_response")
    if rpc is None:
        return result
    if not isinstance(rpc, dict):
        raise ValueError("RPC evidence must be a JSON object")
    try:
        account = rpc["result"]["value"]
        owner = account["owner"]
        parsed = account["data"]["parsed"]
        info = parsed["info"]
    except (TypeError, KeyError) as exc:
        raise ValueError("Unsupported jsonParsed getAccountInfo structure") from exc
    if owner not in TOKEN_PROGRAMS or parsed.get("type") != "mint" or not isinstance(info, dict):
        raise ValueError("Not a recognised SPL token mint account")
    if ("mintAuthority" not in info or "freezeAuthority" not in info or
            not isinstance(info.get("decimals"), int) or
            not 0 <= info["decimals"] <= 18 or
            not isinstance(info.get("supply"), str) or
            not info["supply"].isdigit()):
        raise ValueError("Missing or invalid SPL mint fields")
    for key in ("mintAuthority", "freezeAuthority"):
        value = info[key]
        if value is not None and not _valid_mint(value):
            raise ValueError("Invalid authority address in supplied evidence")
    result.update(
        provenance="user_supplied_unverified_jsonparsed_rpc",
        token_program=TOKEN_PROGRAMS[owner],
        authority_check="parsed_unverified",
        mint_authority_active=info["mintAuthority"] is not None,
        freeze_authority_active=info["freezeAuthority"] is not None,
    )
    if info["mintAuthority"] is not None:
        result["warnings"].append("Mint authority is present in supplied evidence.")
    if info["freezeAuthority"] is not None:
        result["warnings"].append("Freeze authority is present in supplied evidence.")
    if owner != next(iter(TOKEN_PROGRAMS)):
        result["warnings"].append("Token-2022 extensions and authorities were not audited.")
    return result
