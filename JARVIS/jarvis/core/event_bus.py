from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any]


@dataclass
class Subscription:
    event_name: str
    queue: asyncio.Queue[Event]


class EventBus:
    """In-process async pub/sub with bounded subscriber queues."""

    def __init__(self, queue_size: int = 100):
        self.queue_size = queue_size
        self._subscriptions: dict[str, set[asyncio.Queue[Event]]] = {}
        self._lock = asyncio.Lock()
        self.dropped_events = 0

    async def subscribe(self, event_name: str) -> Subscription:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self.queue_size)
        async with self._lock:
            self._subscriptions.setdefault(event_name, set()).add(queue)
        return Subscription(event_name, queue)

    async def unsubscribe(self, subscription: Subscription) -> None:
        async with self._lock:
            queues = self._subscriptions.get(subscription.event_name)
            if queues:
                queues.discard(subscription.queue)
                if not queues:
                    self._subscriptions.pop(subscription.event_name, None)

    async def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> int:
        event = Event(event_name, payload or {})
        async with self._lock:
            queues = tuple(self._subscriptions.get(event_name, ())) + tuple(self._subscriptions.get("*", ()))
        delivered = 0
        for queue in queues:
            try:
                queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                self.dropped_events += 1
        return delivered
