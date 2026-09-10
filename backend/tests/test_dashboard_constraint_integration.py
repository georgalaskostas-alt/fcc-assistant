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
                {"id": "fcc-feed", "type": "trend", "unit_key": "fcc", "title": "FCC Feed", "period": "8h", "tag_keys": ["feed_flow"]},
                {"id": "hcu-feed", "type": "trend", "unit_key": "hcu", "title": "HCU Feed", "period": "8h", "tag_keys": ["hcu_feed_flow"]},
            ],
        }

    def get(self, workspace):
        return self.current

    def apply_plan(self, workspace, plan):
        self.mutated = True
        if plan.get("action") == "add_widget":
            self.current = {**self.current, "widgets": [*self.current["widgets"], dict(plan["widget"])]}
        return self.current

    def apply_transaction(self, workspace, plans):
        self.mutated = True
        for plan in plans:
            if plan.get("action") == "add_widget":
                self.current = {**self.current, "widgets": [*self.current["widgets"], dict(plan["widget"])]}
        return self.current


class FakeDialogue:
    def aliases(self): return {}
    def remember_requested_unit(self, workspace, unit_key): pass
    def get_state(self, workspace): return {}
    def get_action_context(self, workspace): return {}
    def remember(self, *args, **kwargs): pass


class FakePending:
    def get(self, workspace): return None
    def set(self, workspace, frame): pass
    def clear(self, workspace): pass


def _prepare(monkeypatch, plan):
    store = FakeStore()

    async def fake_agent(command, site, state, widgets):
        return AgentResult(plan=plan, message="stale model confirmation")

    monkeypatch.setattr(dashboard_api, "DashboardStore", lambda: store)
    monkeypatch.setattr(dashboard_api, "DashboardDialogueStore", lambda: FakeDialogue())
    monkeypatch.setattr(dashboard_api, "DashboardPendingStore", lambda: FakePending())
    monkeypatch.setattr(dashboard_api, "plan_with_local_agent", fake_agent)
    monkeypatch.setattr(dashboard_api, "site_runtime_status", lambda: {"read_only": True})
    return store


def test_api_blocks_wrong_unit_when_replan_is_also_unsafe(monkeypatch):
    wrong = {"action": "remove_widget", "target_id": "hcu-feed", "read_only": True, "requires_confirmation": False}
    store = _prepare(monkeypatch, wrong)
    monkeypatch.setattr(dashboard_api, "_legacy_plan", lambda *args, **kwargs: (wrong, None))

    result = asyncio.run(
        dashboard_api._execute_dashboard_command(
            DashboardCommandRequest(command="Αφαίρεσε το feed από το FCC", workspace="default")
        )
    )

    assert result["plan"]["action"] == "clarify"
    assert result["needs_clarification"] is True
    assert store.mutated is False


def test_bad_llm_action_is_replanned_and_executed_safely(monkeypatch):
    store = _prepare(
        monkeypatch,
        {"action": "update_widgets", "target_ids": ["fcc-feed", "hcu-feed"], "period": "4h", "read_only": True, "requires_confirmation": False},
    )
    safe = {
        "action": "add_widget",
        "widget": {"id": "fcc-feed-new", "type": "trend", "unit_key": "fcc", "title": "Feed Flow", "tag_keys": ["feed_flow"], "period": "8h"},
        "read_only": True,
        "requires_confirmation": False,
    }
    monkeypatch.setattr(dashboard_api, "_legacy_plan", lambda *args, **kwargs: (safe, None))

    result = asyncio.run(
        dashboard_api._execute_dashboard_command(
            DashboardCommandRequest(command="Βάλε ένα διάγραμμα feed flow στο FCC", workspace="default")
        )
    )

    assert result["plan"]["action"] == "add_widget"
    assert result["agent"] == "constraint-recovered-fallback"
    assert result["needs_clarification"] is False
    assert store.mutated is True
    assert any(w["id"] == "fcc-feed-new" for w in result["workspace"]["widgets"])
    assert "Πρόσθεσα 1" in result["message"]
    assert "stale model confirmation" not in result["message"]


def test_bad_llm_english_action_recovers_and_confirmation_is_english(monkeypatch):
    store = _prepare(
        monkeypatch,
        {"action": "update_widgets", "target_ids": ["hcu-feed"], "period": "4h", "read_only": True, "requires_confirmation": False},
    )
    safe = {
        "action": "add_widget",
        "widget": {"id": "fcc-en-new", "type": "trend", "unit_key": "fcc", "title": "Feed Flow", "tag_keys": ["feed_flow"], "period": "8h"},
        "read_only": True,
        "requires_confirmation": False,
    }
    monkeypatch.setattr(dashboard_api, "_legacy_plan", lambda *args, **kwargs: (safe, None))

    result = asyncio.run(
        dashboard_api._execute_dashboard_command(
            DashboardCommandRequest(command="Add a feed flow chart to FCC", workspace="default")
        )
    )
    assert store.mutated is True
    assert result["language"] == "en"
    assert result["message"].startswith("Added 1 widget")
