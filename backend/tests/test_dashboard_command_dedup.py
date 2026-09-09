import asyncio

from app import dashboard_api
from app.dashboard_api import DashboardCommandRequest


def test_same_command_is_executed_once(monkeypatch):
    calls=0

    async def fake_execute(request):
        nonlocal calls
        calls+=1
        await asyncio.sleep(0.01)
        return {"plan":{"action":"answer","read_only":True},"workspace":{"workspace":"default","title":"x","widgets":[]},"message":"ok"}

    monkeypatch.setattr(dashboard_api,"_execute_dashboard_command",fake_execute)
    dashboard_api._command_cache.clear()
    dashboard_api._command_gate=None

    async def run():
        request=DashboardCommandRequest(command="Βάλε feed flow στο FCC",workspace="default")
        return await asyncio.gather(*(dashboard_api.dashboard_command(request) for _ in range(8)))

    results=asyncio.run(run())
    assert calls==1
    assert len(results)==8
    assert all(result["message"]=="ok" for result in results)


def test_different_commands_are_not_deduplicated(monkeypatch):
    calls=0

    async def fake_execute(request):
        nonlocal calls
        calls+=1
        return {"plan":{"action":"answer","read_only":True},"workspace":{"workspace":"default","title":"x","widgets":[]},"message":request.command}

    monkeypatch.setattr(dashboard_api,"_execute_dashboard_command",fake_execute)
    dashboard_api._command_cache.clear()
    dashboard_api._command_gate=None

    async def run():
        return await asyncio.gather(
            dashboard_api.dashboard_command(DashboardCommandRequest(command="command one")),
            dashboard_api.dashboard_command(DashboardCommandRequest(command="command two")),
        )

    asyncio.run(run())
    assert calls==2
