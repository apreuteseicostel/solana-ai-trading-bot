"""Read-only PumpPortal WebSocket transport with bounded retries.

This module NEVER submits orders or signs transactions.
"""
import asyncio
import json
from collections.abc import Callable
from typing import Any

from .scanner import TokenCreated, parse_token_creation

PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"


def subscribe_message() -> str:
    return json.dumps({"method": "subscribeNewToken"})


async def listen_new_tokens(
    on_event: Callable[[TokenCreated], Any],
    url: str = PUMPPORTAL_WS,
    max_retries: int = 5,
    max_events: int | None = None,
) -> int:
    """Read token creation events; reconnect on transport failures.

    Requires optional `websockets` dependency. Use max_events for bounded runs.
    No token metadata URLs are fetched or executed.
    """
    if max_retries < 0 or (max_events is not None and max_events <= 0):
        raise ValueError("Invalid retry or event limit")
    import websockets

    received = 0
    failures = 0
    while True:
        try:
            async with websockets.connect(
                url, open_timeout=10, close_timeout=5, max_size=262144
            ) as socket:
                await socket.send(subscribe_message())
                failures = 0
                async for message in socket:
                    try:
                        payload = json.loads(message)
                    except (ValueError, TypeError):
                        continue
                    event = parse_token_creation(payload)
                    if event is None:
                        continue
                    on_event(event)
                    received += 1
                    if max_events is not None and received >= max_events:
                        return received
        except (OSError, TimeoutError, websockets.exceptions.WebSocketException):
            failures += 1
            if failures > max_retries:
                raise
            await asyncio.sleep(min(2 ** (failures - 1), 30))
