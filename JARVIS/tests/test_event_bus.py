import asyncio

from jarvis.core.event_bus import EventBus


def test_publish_reaches_named_and_wildcard_subscribers():
    async def scenario():
        bus = EventBus()
        named = await bus.subscribe("updates")
        wildcard = await bus.subscribe("*")
        assert await bus.publish("updates", {"value": 3}) == 2
        assert (await named.queue.get()).payload == {"value": 3}
        assert (await wildcard.queue.get()).name == "updates"
    asyncio.run(scenario())


def test_bounded_queue_drops_without_blocking():
    async def scenario():
        bus = EventBus(queue_size=1)
        sub = await bus.subscribe("x")
        await bus.publish("x")
        await bus.publish("x")
        assert bus.dropped_events == 1
        assert sub.queue.qsize() == 1
    asyncio.run(scenario())
