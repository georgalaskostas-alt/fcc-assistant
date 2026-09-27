import asyncio

from backend.app.active_identity import ActiveIdentity
from backend.app import investigation_api
from backend.app.investigation_api import InvestigationContinueRequest


def test_continue_request_contract():
    request = InvestigationContinueRequest(
        utterance="συνέχισε το θέμα με το regenerator",
        unit_key="fcc",
    )
    assert request.unit_key == "fcc"
    assert "regenerator" in request.utterance


def test_continue_endpoint_passes_server_owned_identity_to_local_context(monkeypatch):
    identity = ActiveIdentity(
        actor_id="alice",
        source="test",
        authenticated=True,
        unit_ids=frozenset({"fcc"}),
    )
    sentinel_context = object()
    captured = {}

    monkeypatch.setattr(investigation_api, "active_identity", lambda: identity)
    monkeypatch.setattr(
        investigation_api,
        "investigation_tag_service",
        lambda: (object(), {"mode": "simulated", "data_quality": "SIMULATED"}),
    )
    monkeypatch.setattr(
        investigation_api,
        "build_refinery_tool_registry",
        lambda tag_service: object(),
    )

    def fake_local_context(received_identity, unit_key):
        captured["identity"] = received_identity
        captured["unit_key"] = unit_key
        return sentinel_context

    monkeypatch.setattr(investigation_api, "_local_context", fake_local_context)

    class FakeService:
        def __init__(self, *, registry, store):
            pass

        async def continue_from_conversation(self, **kwargs):
            captured["service_context"] = kwargs["context"]
            captured["user_id"] = kwargs["user_id"]
            return {"status": "continued"}

    monkeypatch.setattr(investigation_api, "InvestigationService", FakeService)
    monkeypatch.setattr(investigation_api, "InvestigationStore", lambda: object())

    result = asyncio.run(
        investigation_api.continue_investigation(
            InvestigationContinueRequest(
                utterance="continue the saved investigation",
                unit_key="fcc",
            )
        )
    )

    assert captured["identity"] is identity
    assert captured["unit_key"] == "fcc"
    assert captured["service_context"] is sentinel_context
    assert captured["user_id"] == "alice"
    assert result["status"] == "continued"


def test_run_endpoint_persists_initial_dynamic_investigation(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from backend.app import investigation_api

    identity = ActiveIdentity(
        actor_id="alice",
        source="test",
        authenticated=True,
        unit_ids=frozenset({"fcc"}),
    )
    store_path = tmp_path / "investigations.json"
    real_store = investigation_api.InvestigationStore
    monkeypatch.setattr(investigation_api, "active_identity", lambda: identity)
    monkeypatch.setattr(investigation_api, "InvestigationStore", lambda: real_store(store_path))
    monkeypatch.setattr(
        investigation_api,
        "investigation_tag_service",
        lambda: (object(), {"mode":"simulated","data_quality":"SIMULATED"}),
    )
    monkeypatch.setattr(investigation_api, "build_refinery_tool_registry", lambda tag_service: object())
    monkeypatch.setattr(investigation_api, "runtime_build_identity", lambda: "test-build")
    monkeypatch.setattr(investigation_api, "append_trace", lambda *args, **kwargs: None)

    synthesis = {
        "unit_key":"fcc",
        "time_window":{"start":"2026-09-24T00:00:00Z","end":"2026-09-25T00:00:00Z"},
        "resolved_tags":["regenerator_dp"],
        "last_autonomous_focus":"regenerator dp",
        "autonomous_rounds_completed":1,
        "evidence_count":1,
        "evidence_package":[{
            "evidence_id":"get_history:history-0",
            "tool":"get_history",
            "description":"Regenerator DP history",
            "data":{"tag_key":"regenerator_dp","values":[{"value":0.9}]},
            "provenance":{"source":"test"},
        }],
        "discovery_evidence":[],
        "ready_for_reasoning":True,
    }

    class FakeDynamicInvestigator:
        def __init__(self, registry):
            pass
        async def investigate(self, **kwargs):
            return SimpleNamespace(discovery={}, analysis={}, synthesis=synthesis)

    async def fake_reasoning(**kwargs):
        return {"text":"bounded result","claims":[],"investigation_trail":{"stop_reason":"evidence_saturated"}}

    monkeypatch.setattr(investigation_api, "DynamicInvestigator", FakeDynamicInvestigator)
    monkeypatch.setattr(investigation_api, "reason_about_investigation", fake_reasoning)
    monkeypatch.setattr(investigation_api, "validate_engineering_narrative", lambda *args, **kwargs: {"valid":True,"violations":[]})

    result = asyncio.run(
        investigation_api.run_investigation(
            investigation_api.InvestigationRequest(goal="Why did DP rise?",unit_key="fcc")
        )
    )

    saved = real_store(store_path).list(user_id="alice")
    assert len(saved) == 1
    assert saved[0].status.value == "waiting"
    assert saved[0].resume_context["resolved_tags"] == ["regenerator_dp"]
    assert saved[0].resume_context["evidence_count"] == 1
    assert len(saved[0].evidence) == 1
    assert result["investigation"]["id"] == saved[0].id
