"""Bounded, retrospective SIGNAL view of recorded paper decisions.

This module never recommends or places an order. In particular, a historical paper
fill must not be represented as a current executable signal.
"""

MAX_SIGNALS = 200


def signal_feed(decisions, *, limit=MAX_SIGNALS):
    """Project newest-first recorded paper decisions without claiming live signals."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_SIGNALS:
        raise ValueError("signal limit must be 1..200")
    result = []
    for item in decisions[:limit]:
        if not isinstance(item, dict) or item.get("mode") != "paper":
            continue
        status = item.get("status")
        classification = {
            "filled": "historical_paper_fill",
            "rejected": "historical_rejection",
        }.get(status, "historical_other")
        side = item.get("side")
        if side not in ("BUY", "SELL"):
            side = None
        result.append({
            "wallet": item.get("wallet"),
            "signature": item.get("signature"),
            "at": item.get("at"),
            "source": item.get("source") or "unknown",
            "classification": classification,
            "side": side,
            "reason": item.get("reason") or "not_recorded",
            "actionable": False,
            "execution": "paper_only",
        })
    return result
