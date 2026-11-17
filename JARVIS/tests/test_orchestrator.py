import asyncio


def test_route_greeting(core):
    async def scenario():
        result = await core.route("Hello Jarvis")
        assert result["status"] == "completed"
        assert result["output"] == "At your service, sir."
    asyncio.run(scenario())


def test_unknown_request_is_not_run_as_a_plan(core):
    async def scenario():
        result = await core.route("delete every file")
        assert result["status"] == "unmatched"
    asyncio.run(scenario())


def test_manifest_discovery_loads_skills(core):
    assert {manifest.name for manifest in core.registry.list()} == {"demo", "system"}
