import asyncio

import pytest

from solana_ai_bot.live_feed import listen_new_tokens
from solana_ai_bot.market_data import load_price_csv


@pytest.mark.parametrize(
    "text",
    [
        "mint,timestamp,price,price\nM,1,2,3\n",
        "mint,timestamp,price\nM,1,2,extra\n",
        "mint,timestamp,price\nM,1\n",
    ],
)
def test_csv_duplicate_headers_or_ragged_rows_rejected(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text)
    with pytest.raises(ValueError):
        load_price_csv(path)


def test_handshake_disconnect_cycles_exhaust_total_budget(monkeypatch):
    import websockets

    attempts = []
    sleeps = []

    class Disconnecting:
        async def __aenter__(self):
            attempts.append(1)
            return self

        async def __aexit__(self, *args):
            pass

        async def send(self, message):
            pass

        async def recv(self):
            raise OSError("disconnected after handshake")

    async def no_wait(delay):
        sleeps.append(delay)

    monkeypatch.setattr(websockets, "connect", lambda *args, **kwargs: Disconnecting())
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    with pytest.raises(OSError):
        asyncio.run(listen_new_tokens(lambda _: None, max_retries=2))
    assert len(attempts) == 3
    assert sleeps == [1, 2]


def test_absolute_deadline_bounds_idle_connection(monkeypatch):
    import websockets

    class Idle:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def send(self, message):
            pass

        async def recv(self):
            await asyncio.Event().wait()

    monkeypatch.setattr(websockets, "connect", lambda *args, **kwargs: Idle())
    with pytest.raises(TimeoutError):
        asyncio.run(listen_new_tokens(lambda _: None, max_duration=0.01))
