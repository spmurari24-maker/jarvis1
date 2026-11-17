from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class PendingConfirmation:
    confirmation_id: str
    skill_name: str
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    expires_at: float


class ConfirmationManager:
    def __init__(self, ttl_seconds: int = 180):
        self.ttl_seconds = ttl_seconds
        self._pending: dict[str, PendingConfirmation] = {}

    def create(self, skill_name: str, tool_name: str, arguments: dict[str, Any], summary: str) -> PendingConfirmation:
        self._expire()
        item = PendingConfirmation(secrets.token_urlsafe(24), skill_name, tool_name, arguments,
                                   summary, time.monotonic() + self.ttl_seconds)
        self._pending[item.confirmation_id] = item
        return item

    def consume(self, confirmation_id: str) -> PendingConfirmation:
        item = self._pending.pop(confirmation_id, None)
        if item is None or item.expires_at < time.monotonic():
            raise KeyError("Confirmation is unknown or expired")
        return item

    def clear(self) -> int:
        count = len(self._pending)
        self._pending.clear()
        return count

    def _expire(self) -> None:
        now = time.monotonic()
        self._pending = {key: value for key, value in self._pending.items() if value.expires_at >= now}
