import json
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from solana_ai_bot.intel_http import JsonTransport, NoRedirect, ProviderError

URL = "https://api.jup.ag/swap/v2/order?inputMint=public"


class Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return Response(value)


def test_retries_obey_total_budget_and_redact_url():
    sleeps, requests = [], []
    transport = JsonTransport(
        max_requests=2,
        retries=3,
        sleep=sleeps.append,
        on_request=lambda host, at: requests.append(host),
    )
    transport.opener = Opener([URLError("secret-in-exception")] * 2)
    with pytest.raises(ProviderError) as error:
        transport.request("GET", URL + "&api-key=not-a-real-key")
    assert "not-a-real-key" not in str(error.value)
    assert "secret-in-exception" not in str(error.value)
    assert len(transport.opener.calls) == 2
    assert requests == ["api.jup.ag", "api.jup.ag"]
    assert max(sleeps) <= 4


@pytest.mark.parametrize(
    "status,retried", [(429, True), (503, True), (401, False), (400, False)]
)
def test_retryable_statuses(status, retried):
    transport = JsonTransport(retries=1, sleep=lambda _: None)
    transport.opener = Opener([HTTPError(URL, status, "no", {}, None), b'{"ok":true}'])
    if retried:
        assert transport.request("GET", URL) == {"ok": True}
        assert transport.requests == 2
    else:
        with pytest.raises(ProviderError):
            transport.request("GET", URL)
        assert transport.requests == 1


@pytest.mark.parametrize(
    "url,method",
    [
        ("https://api.jup.ag/swap/v2/execute", "POST"),
        ("http://api.jup.ag/swap/v2/order", "GET"),
        ("https://evil.example/swap/v2/order", "GET"),
        ("https://api.jup.ag:444/swap/v2/order", "GET"),
        ("https://mainnet.helius-rpc.com/", "POST"),
    ],
)
def test_no_execution_or_arbitrary_endpoints(url, method):
    transport = JsonTransport()
    with pytest.raises(ProviderError, match="allowlist"):
        transport.request(method, url)
    assert transport.requests == 0


def test_redirects_disabled():
    with pytest.raises(ProviderError):
        NoRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://evil.example"
        )


@pytest.mark.parametrize("content", [b"not json", b"[]", b"x" * 4_000_001])
def test_response_limits(content):
    transport = JsonTransport()
    transport.opener = Opener([content])
    with pytest.raises(ProviderError):
        transport.request("GET", URL)


def test_history_is_posted_as_json_without_wallet_keys():
    transport = JsonTransport()
    transport.opener = Opener([b'{"data":[]}'])
    transport.request(
        "POST",
        "https://mainnet.helius-rpc.com/v1/parsed-events/transaction-history",
        body={"address": "public", "commitment": "finalized"},
    )
    assert json.loads(transport.opener.calls[0].data) == {
        "address": "public",
        "commitment": "finalized",
    }
