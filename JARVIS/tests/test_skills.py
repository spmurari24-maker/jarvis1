import asyncio
import pytest


def test_demo_echo_validates_input(core):
    async def scenario():
        result = await core.invoke("demo", "echo", {"text": "diagnostic"})
        assert result["output"] == "diagnostic"
        with pytest.raises(ValueError):
            await core.invoke("demo", "echo", {"text": "x" * 4001})
    asyncio.run(scenario())


def test_system_status_is_read_only(core):
    async def scenario():
        result = await core.invoke("system", "status")
        assert result["output"] == {"status": "ready", "offline_safe": True}
    asyncio.run(scenario())


def test_skill_can_publish_events(core):
    async def scenario():
        subscription = await core.event_bus.subscribe("demo.message")
        result = await core.invoke("demo", "publish_event", {
            "event": "demo.message", "payload": {"value": "hello"}
        })
        event = await subscription.queue.get()
        assert result["output"]["delivered"] == 1
        assert event.payload["value"] == "hello"
    asyncio.run(scenario())
