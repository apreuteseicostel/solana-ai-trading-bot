"""Jupiter Swap V2 quote-only adapter. No taker, transaction construction or execute API."""

from urllib.parse import urlencode

from .intel_http import ProviderError
from .intel_models import Quote, address, decimal, integer


class JupiterQuotes:
    def __init__(self, api_key, transport):
        if not api_key or not api_key.strip():
            raise ValueError("JUPITER_API_KEY is required")
        self._key = api_key
        self.transport = transport

    def quote(self, input_mint, output_mint, amount, *, now, slippage_bps=50):
        address(input_mint)
        address(output_mint)
        integer(amount, positive=True)
        integer(slippage_bps)
        if slippage_bps > 500:
            raise ValueError("slippage_bps must be 0..500")
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
        }
        data = self.transport.request(
            "GET",
            "https://api.jup.ag/swap/v2/order?" + urlencode(params),
            headers={"x-api-key": self._key},
        )
        try:
            if data.get("error") or data.get("errorCode") or data.get("transaction"):
                raise ValueError("Unexpected quote response")
            if (data.get("inputMint"), data.get("outputMint")) != (
                input_mint,
                output_mint,
            ):
                raise ValueError("Mint mismatch")
            if integer(data["inAmount"], positive=True) != amount:
                raise ValueError("Amount mismatch")
            if data.get("swapMode") != "ExactIn":
                raise ValueError("Only ExactIn quotes are supported")
            output_raw = integer(data["outAmount"], positive=True)
            minimum_raw = integer(data["otherAmountThreshold"], positive=True)
            if minimum_raw < output_raw * (10000 - slippage_bps) // 10000:
                raise ValueError("Quote exceeds requested slippage envelope")
            # V2 priceImpact is percentage points; do NOT apply V1 ratio semantics.
            platform = data.get("platformFee") or {}
            if not isinstance(platform, dict):
                raise TypeError("Invalid platform fee")
            return Quote(
                input_mint,
                output_mint,
                amount,
                output_raw,
                minimum_raw,
                decimal(data["priceImpact"]),
                integer(now),
                integer(data.get("contextSlot", 0)),
                fee_bps=integer(data.get("feeBps", 0)),
                platform_fee_raw=integer(platform.get("amount", 0)),
                platform_fee_mint=platform.get("feeMint") or data.get("feeMint") or "",
            )
        except (KeyError, TypeError, ValueError):
            raise ProviderError("Invalid Jupiter quote; no simulated fill") from None
