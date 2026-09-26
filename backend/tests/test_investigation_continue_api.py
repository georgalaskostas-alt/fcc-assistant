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
