import asyncio
import pytest


def test_risky_tool_waits_for_explicit_approval_then_runs(core):
    async def scenario():
        request = await core.invoke("demo", "demo_critical_action")
        assert request["status"] == "confirmation_required"
        result = await core.confirm(request["confirmation_id"])
        assert result["status"] == "completed"
        assert "no external system" in result["output"]
    asyncio.run(scenario())


def test_confirmation_is_one_time(core):
    async def scenario():
        request = await core.invoke("demo", "demo_critical_action")
        await core.confirm(request["confirmation_id"])
        with pytest.raises(KeyError):
            await core.confirm(request["confirmation_id"])
    asyncio.run(scenario())
