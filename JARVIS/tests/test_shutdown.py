import pytest
import asyncio

from jarvis.core.shutdown import SystemHalted


def test_shutdown_requires_exact_phrase_and_blocks_calls(core):
    async def scenario():
        with pytest.raises(ValueError):
            await core.shutdown_all("shutdown")
        result = await core.shutdown_all("Jarvis, shutdown protocol")
        assert result["status"] == "halted"
        with pytest.raises(SystemHalted):
            await core.invoke("system", "status")
    asyncio.run(scenario())


def test_shutdown_cancels_running_async_tool(core):
    async def scenario():
        started = asyncio.Event()
        async def wait_forever(tool_name, arguments, context):
            started.set()
            await asyncio.Event().wait()
        core.registry.get("demo").execute = wait_forever
        action = asyncio.create_task(core.invoke("demo", "greet"))
        await started.wait()
        result = await core.shutdown_all("Jarvis, shutdown protocol")
        assert result["cancelled_tasks"] == 1
        with pytest.raises(asyncio.CancelledError):
            await action
    asyncio.run(scenario())
