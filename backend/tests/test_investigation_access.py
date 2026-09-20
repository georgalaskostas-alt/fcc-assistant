from backend.app.investigation_access import authorize_investigation,visible_investigations,InvestigationAccessError
from backend.app.investigation_store import Investigation
from backend.app.agent_tools import ToolContext
from backend.app.refinery_model import AccessGrant,DataDomain,RefineryScope,ScopeKind,UnitScope

def _context(actor="alice",units=frozenset({"fcc"})):
    refinery=RefineryScope(id="site",name="Site",standalone_units=(UnitScope(id="fcc",name="FCC"),UnitScope(id="hcu",name="HCU")))
    access=AccessGrant(domains=frozenset({DataDomain.PROCESS}),unit_ids=units)
    return ToolContext(actor_id=actor,refinery=refinery,access=access,scope_kind=ScopeKind.UNIT,scope_id="fcc")

def test_other_users_investigation_is_hidden():
    item=Investigation(id="i",goal="g",user_id="bob",unit_key="fcc")
    try: authorize_investigation(item,_context())
    except InvestigationAccessError: pass
    else: raise AssertionError("cross-user investigation must be denied")

def test_other_unit_investigation_is_hidden():
    item=Investigation(id="i",goal="g",user_id="alice",unit_key="hcu")
    assert visible_investigations([item],_context())==[]

def test_authorized_unit_is_visible():
    item=Investigation(id="i",goal="g",user_id="alice",unit_key="fcc")
    assert visible_investigations([item],_context())==[item]
