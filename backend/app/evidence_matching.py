"""Conservative matching of independent evidence to investigation hypotheses.

This module does not decide causality. It only records whether source text shares
specific engineering terms with a hypothesis and therefore deserves review.
"""
from __future__ import annotations
import re
from typing import Any

_STOP = {"the","and","for","with","from","whether","observed","relationship","between","independent","process","explanation","investigate","this","that","into","have","has"}

def _terms(text: str) -> set[str]:
    return {w.casefold() for w in re.findall(r"[A-Za-z0-9_.-]{3,}", text) if w.casefold() not in _STOP}

_SUPPORT = {"associated","association","accompanied","increase","increased","decrease","decreased","high","low","rise","rises","rose","drop","dropped","response","related"}
_CONTRADICT = {"not","no","without","unrelated","independent","unchanged","stable","normal","excluded","exclude","contradicts","contradicted"}

def _match(statement: str, text: str) -> dict[str, Any]:
    common = sorted(_terms(statement).intersection(_terms(text)))
    words = _terms(text)
    matched = len(common) >= 2
    support_hits = sorted(words.intersection(_SUPPORT))
    contradict_hits = sorted(words.intersection(_CONTRADICT))
    if not matched:
        stance = "irrelevant"
    elif contradict_hits and not support_hits:
        stance = "contradicting"
    elif support_hits and not contradict_hits:
        stance = "supporting"
    else:
        stance = "insufficient"
    return {"matched": matched, "matched_terms": common[:12], "stance": stance,
            "support_terms": support_hits[:8], "contradict_terms": contradict_hits[:8]}

def match_hypothesis_evidence(*, hypothesis: dict[str, Any], synthesis: dict[str, Any]) -> dict[str, Any]:
    statement = str(hypothesis.get("statement") or "")
    matches: list[dict[str, Any]] = []

    archive = synthesis.get("archive_evidence") if isinstance(synthesis.get("archive_evidence"), dict) else {}
    for row in archive.get("items", []) if isinstance(archive.get("items"), list) else []:
        if not isinstance(row, dict): continue
        text = " ".join(str(row.get(k) or "") for k in ("title","document_type","text"))
        result = _match(statement, text)
        if result["matched"]:
            matches.append({"source_type":"approved_archive","document_id":row.get("document_id"),"revision":row.get("revision"),"page":row.get("page"),**result})

    events = synthesis.get("event_evidence") if isinstance(synthesis.get("event_evidence"), dict) else {}
    run = events.get("run") if isinstance(events.get("run"), dict) else {}
    executions = run.get("executions") if isinstance(run.get("executions"), dict) else {}
    execution = executions.get("search-events") if isinstance(executions.get("search-events"), dict) else {}
    result_obj = execution.get("result") if isinstance(execution.get("result"), dict) else {}
    for row in result_obj.get("data", []) if isinstance(result_obj.get("data"), list) else []:
        if not isinstance(row, dict): continue
        text = " ".join(str(row.get(k) or "") for k in ("event_type","message","tag_key","equipment_key"))
        result = _match(statement, text)
        if result["matched"]:
            matches.append({"source_type":"alarm_event","event_id":row.get("id"),"timestamp":row.get("timestamp"),**result})

    similar = synthesis.get("similar_episodes") if isinstance(synthesis.get("similar_episodes"), dict) else {}
    for row in similar.get("items", []) if isinstance(similar.get("items"), list) else []:
        if not isinstance(row, dict): continue
        episode = row.get("episode") if isinstance(row.get("episode"), dict) else {}
        text = " ".join([str(episode.get("kind") or ""),str(episode.get("regime") or "")," ".join(map(str,row.get("matched_features") or []))])
        result = _match(statement, text)
        if result["matched"]:
            matches.append({"source_type":"historical_episode","episode_id":episode.get("id"),"similarity":row.get("similarity"),**result})

    supporting = [m for m in matches if m.get("stance") == "supporting"]
    contradicting = [m for m in matches if m.get("stance") == "contradicting"]
    insufficient = [m for m in matches if m.get("stance") == "insufficient"]
    return {"matches": matches, "match_count": len(matches),
            "supporting": supporting, "contradicting": contradicting, "insufficient": insufficient,
            "interpretation": "relevant_for_review" if matches else "no_specific_match"}
