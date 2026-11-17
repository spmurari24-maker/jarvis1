from __future__ import annotations

import asyncio
import time
from collections import deque


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: float):
        super().__init__("Request rate limit exceeded")
        self.retry_after = max(0.0, retry_after)


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            hits = self._hits.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                raise RateLimitExceeded(self.window_seconds - (now - hits[0]))
            hits.append(now)
