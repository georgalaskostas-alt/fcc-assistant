from backend.app.active_identity import active_identity

def test_active_identity_is_server_owned(monkeypatch):
    monkeypatch.setenv("FCC_ASSISTANT_ACTOR_ID","engineer-a")
    identity=active_identity()
    assert identity.actor_id=="engineer-a"
    assert identity.source=="phase1-local-server"

def test_active_identity_has_safe_local_default(monkeypatch):
    monkeypatch.delenv("FCC_ASSISTANT_ACTOR_ID",raising=False)
    assert active_identity().actor_id=="local-engineer"
