import pytest
from backend.app.active_identity import ActiveIdentity
from backend.app.investigation_api import _local_context

def test_identity_grant_allows_only_server_owned_units():
    identity=ActiveIdentity(actor_id="alice",source="test",authenticated=True,unit_ids=frozenset({"fcc"}))
    context=_local_context(identity,"fcc")
    assert context.actor_id=="alice"
    assert context.scope_id=="fcc"
    assert context.access.unit_ids==frozenset({"fcc"})

def test_client_cannot_select_unit_outside_identity_grant():
    identity=ActiveIdentity(actor_id="alice",source="test",authenticated=True,unit_ids=frozenset({"fcc"}))
    with pytest.raises(PermissionError):
        _local_context(identity,"hcu")
