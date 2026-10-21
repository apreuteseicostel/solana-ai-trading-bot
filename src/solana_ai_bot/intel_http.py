"""Fixed-host HTTPS JSON transport. No signing, redirects, or execution endpoints."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ProviderError(RuntimeError):
    """Deliberately contains no response body, credential, or full URL."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError("Provider redirects are disabled")


class JsonTransport:
    def __init__(
        self,
        *,
        max_requests=100,
        retries=2,
        timeout=10,
        sleep=time.sleep,
        on_request=None,
    ):
        if (
            not 1 <= max_requests <= 10000
            or not 0 <= retries <= 3
            or not 0 < timeout <= 30
        ):
            raise ValueError("Invalid transport limits")
        self.max_requests = max_requests
        self.retries = retries
        self.timeout = timeout
        self.requests = 0
        self.sleep = sleep
        self.opener = build_opener(NoRedirect())
        self.on_request = on_request

    def request(self, method, url, *, headers=None, body=None):
        target = urlsplit(url)
        allowed = {
            ("POST", "mainnet.helius-rpc.com", "/v1/parsed-events/transaction-history"),
            ("GET", "api.jup.ag", "/swap/v2/order"),
        }
        if (
            target.scheme != "https"
            or target.port is not None
            or (method, target.hostname, target.path) not in allowed
        ):
            raise ProviderError("Endpoint is outside the read-only allowlist")
        payload = None if body is None else json.dumps(body).encode()
        for attempt in range(self.retries + 1):
            if self.requests >= self.max_requests:
                raise ProviderError("Provider request budget exhausted")
            self.requests += 1
            if self.on_request:
                self.on_request(target.hostname, int(time.time()))
            request = Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    **(headers or {}),
                },
                method=method,
            )
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    content = response.read(4_000_001)
                    if len(content) > 4_000_000:
                        raise ProviderError("Provider response exceeded size limit")
                    result = json.loads(content)
                    if not isinstance(result, dict):
                        raise ProviderError("Invalid provider response shape")
                    return result
            except HTTPError as exc:
                retry = exc.code in {429, 500, 502, 503, 504}
                delay = min(2**attempt, 4)
                exc.close()
            except (URLError, TimeoutError, OSError):
                retry, delay = True, min(2**attempt, 4)
            except (ValueError, UnicodeError):
                raise ProviderError("Provider returned invalid JSON") from None
            if not retry or attempt == self.retries:
                raise ProviderError(
                    "Provider request failed; check access and service status"
                ) from None
            self.sleep(delay)
        raise ProviderError("Provider request failed")
