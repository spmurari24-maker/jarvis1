import asyncio
import pytest

from jarvis.core.rate_limiter import RateLimitExceeded, RateLimiter


def test_rate_limiter_blocks_after_configured_count():
    async def scenario():
        limiter = RateLimiter(2, 60)
        await limiter.check("client")
        await limiter.check("client")
        with pytest.raises(RateLimitExceeded):
            await limiter.check("client")
    asyncio.run(scenario())
