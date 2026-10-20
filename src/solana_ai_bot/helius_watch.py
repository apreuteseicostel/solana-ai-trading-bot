"""Bounded Helius Parsed Events history. Conservative, wallet-specific swap detection."""

from collections import defaultdict
from urllib.parse import urlencode

from .intel_http import ProviderError
from .intel_models import WalletEvent, address, integer


def normalize(item: dict, wallet: str, observed_at: int) -> WalletEvent:
    """Require a successful swap summary AND matching net token transfers.

    Native SOL legs, multi-asset transactions, sponsored swaps and missing data
    are recorded as ignored, never guessed into trading signals.
    """
    address(wallet)
    if not isinstance(item, dict) or not isinstance(item.get("parsed"), dict):
        raise TypeError("Missing parsed transaction")
    parsed = item["parsed"]
    base = {
        "wallet": wallet,
        "signature": item.get("signature"),
        "slot": integer(parsed.get("slot")),
        "block_time": integer(parsed.get("blockTime")),
        "observed_at": integer(observed_at),
        "network_fee_lamports": integer(parsed.get("fee", 0)),
    }

    def event(kind, reason, **kwargs):
        return WalletEvent(**base, kind=kind, reason=reason, **kwargs)

    if item.get("parserStatus") != "OK" or parsed.get("transactionStatus") != "OK":
        return event("ignored", "parser_or_transaction_not_ok")
    summary = parsed.get("summary") or {}
    if not isinstance(summary, dict):
        return event("ignored", "invalid_summary")
    if summary.get("type") != "swap":
        transfers = {"transfer", "token_transfer", "native_transfer"}
        return event(
            "transfer" if summary.get("type") in transfers else "ignored", "not_a_swap"
        )
    if parsed.get("feePayer") != wallet:
        return event("ignored", "wallet_swap_ownership_not_proven")
    data = summary.get("parsedData")
    if not isinstance(data, dict):
        return event("ignored", "missing_swap_summary")
    try:
        incoming, outgoing = address(data["input_mint"]), address(data["output_mint"])
        amount_in = integer(data["in_amount"], positive=True)
        amount_out = integer(data["actual_out_amount"], positive=True)
        net = defaultdict(int)
        transfers = parsed.get("tokenTransfers")
        if not isinstance(transfers, list):
            raise TypeError("Missing token transfers")
        for transfer in transfers:
            if not isinstance(transfer, dict):
                raise TypeError("Invalid token transfer")
            if wallet not in (
                transfer.get("fromUserAccount"),
                transfer.get("toUserAccount"),
            ):
                continue
            mint = address(transfer["mint"])
            amount = integer(transfer["rawTokenAmount"])
            net[mint] += amount * (
                (transfer.get("toUserAccount") == wallet)
                - (transfer.get("fromUserAccount") == wallet)
            )
        net = {mint: amount for mint, amount in net.items() if amount}
        if net != {incoming: -amount_in, outgoing: amount_out}:
            return event("ignored", "summary_transfer_mismatch_or_native_leg")
        return event(
            "swap",
            "verified_two_token_legs",
            input_mint=incoming,
            output_mint=outgoing,
            input_raw=amount_in,
            output_raw=amount_out,
        )
    except (KeyError, TypeError, ValueError):
        return event("ignored", "unsupported_or_invalid_swap")


class HeliusWatcher:
    def __init__(self, api_key, transport):
        if not api_key or not api_key.strip():
            raise ValueError("HELIUS_API_KEY is required")
        self._key = api_key
        self.transport = transport

    def sync(self, wallet, store, *, observed_at, max_pages=3):
        address(wallet)
        if type(max_pages) is not int or not 1 <= max_pages <= 20:
            raise ValueError("max_pages must be 1..20")
        resume = store.backfill(wallet) or {}
        previous = resume.get("after_signature", store.checkpoint(wallet))
        token = resume.get("pagination_token")
        newest = resume.get("newest_signature")
        seen_tokens = set(resume.get("seen_tokens", []))
        added = 0
        for _ in range(max_pages):
            body = {
                "address": wallet,
                "limit": 100,
                "sortOrder": "desc",
                "commitment": "finalized",
            }
            if previous:
                body["afterSignature"] = previous
            if token:
                body["paginationToken"] = token
            page = self.transport.request(
                "POST",
                "https://mainnet.helius-rpc.com/v1/parsed-events/"
                "transaction-history?" + urlencode({"api-key": self._key}),
                body=body,
            )
            rows = page.get("data")
            if not isinstance(rows, list) or len(rows) > 100:
                raise ProviderError("Invalid history page")
            for item in rows:
                try:
                    observation = normalize(item, wallet, observed_at)
                except (TypeError, ValueError):
                    # Do not advance cursor past data that cannot be journalled.
                    raise ProviderError(
                        "Invalid history item; checkpoint unchanged"
                    ) from None
                if newest is None:
                    newest = observation.signature
                added += store.add_event(observation)
            token = page.get("paginationToken")
            if token is None or token == "":
                if newest:
                    store.set_checkpoint(wallet, newest)
                store.save_backfill(wallet, None)
                return {"new_events": added, "complete": True}
            if (
                not isinstance(token, str)
                or len(token) > 512
                or token in seen_tokens
                or not rows
            ):
                raise ProviderError("Invalid or repeated pagination cursor")
            seen_tokens.add(token)
            if len(seen_tokens) > 1000:
                raise ProviderError(
                    "History continuation limit reached; operator review required"
                )
            store.save_backfill(
                wallet,
                {
                    "after_signature": previous,
                    "pagination_token": token,
                    "newest_signature": newest,
                    "seen_tokens": sorted(seen_tokens),
                },
            )
        # Intentionally leave checkpoint unchanged: next invocation cannot skip history.
        return {"new_events": added, "complete": False, "resume_pending": True}
