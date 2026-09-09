import asyncio

from app import dashboard_api
from app.dashboard_agent import AgentResult
from app.dashboard_api import DashboardCommandRequest


class FakeStore:
    def __init__(self):
        self.mutated = False
        self.current = {
            "workspace": "default",
            "title": "Operations Overview",
            "widgets": [
                {"id": "fcc-feed", "type": "trend", "unit_key": "fcc", "title": "FCC Feed", "period": "8h"},
                {"id": "hcu-feed", "type": "trend", "unit_key": "hcu", "title": "HCU Feed", "period": "8h"},
            ],
        }

    def get(self, workspace):
        return self.current

    def apply_plan(self, workspace, plan):
        self.mutated = True
        raise AssertionError("constraint rejection must happen before dashboard mutation")

    def apply_transaction(self, workspace, plans):
        self.mutated = True
        raise AssertionError("constraint rejection must happen before dashboard mutation")


class FakeDialogue:
    def aliases(self):
        return {}

    def remember_requested_unit(self, workspace, unit_key):
        pass

    def get_state(self, workspace):
        return {}

    def get_action_context(self, workspace):
        return {}

    def remember(self, *args, **kwargs):
        pass


class FakePending:
    def get(self, workspace):
        return None

    def set(self, workspace, frame):
        pass

    def clear(self, workspace):
        pass


def _prepare(monkeypatch, plan):
    store = FakeStore()

    async def fake_agent(command, site, state, widgets):
        return AgentResult(plan=plan, message="ok")

    monkeypatch.setattr(dashboard_api, "DashboardStore", lambda: store)
    monkeypatch.setattr(dashboard_api, "DashboardDialogueStore", lambda: FakeDialogue())
    monkeypatch.setattr(dashboard_api, "DashboardPendingStore", lambda: FakePending())
    monkeypatch.setattr(dashboard_api, "plan_with_local_agent", fake_agent)
    monkeypatch.setattr(dashboard_api, "site_runtime_status", lambda: {"read_only": True})
    return store


def test_api_rejects_wrong_unit_without_mutating_dashboard(monkeypatch):
    store = _prepare(
        monkeypatch,
        {"action": "remove_widget", "target_id": "hcu-feed", "read_only": True, "requires_confirmation": False},
    )

    result = asyncio.run(
        dashboard_api._execute_dashboard_command(
            DashboardCommandRequest(command="Αφαίρεσε το feed από το FCC", workspace="default")
        )
    )

    assert result["plan"]["action"] == "clarify"
    assert result["needs_clarification"] is True
    assert result["workspace"] == store.current
    assert store.mutated is False


def test_api_rejects_wrong_action_without_mutating_dashboard(monkeypatch):
    store = _prepare(
        monkeypatch,
        {
            "action": "update_widgets",
            "target_ids": ["fcc-feed"],
            "period": "16h",
            "read_only": True,
            "requires_confirmation": False,
        },
    )

    result = asyncio.run(
        dashboard_api._execute_dashboard_command(
            DashboardCommandRequest(command="Βάλε ένα διάγραμμα feed στο FCC", workspace="default")
        )
    )

    assert result["plan"]["action"] == "clarify"
    assert result["needs_clarification"] is True
    assert result["workspace"] == store.current
    assert store.mutated is False
