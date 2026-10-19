import json

import pytest
from solana_ai_bot.live_feed import listen_new_tokens, subscribe_message


def test_subscription_is_read_only():
    assert json.loads(subscribe_message()) == {"method": "subscribeNewToken"}


@pytest.mark.asyncio
async def test_reject_invalid_limits():
    with pytest.raises(ValueError):
        await listen_new_tokens(lambda event: None, max_retries=-1)
    with pytest.raises(ValueError):
        await listen_new_tokens(lambda event: None, max_events=0)
