from backend.app.investigation_api import InvestigationContinueRequest

def test_continue_request_contract():
    request=InvestigationContinueRequest(utterance="συνέχισε το θέμα με το regenerator",unit_key="fcc")
    assert request.unit_key=="fcc"
    assert request.user_id=="eng"
    assert "regenerator" in request.utterance
