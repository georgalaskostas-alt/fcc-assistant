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

def _match(statement: str, text: str) -> dict[str, Any]:
    common = sorted(_terms(statement).intersection(_terms(text)))
    return {"matched": len(common) >= 2, "matched_terms": common[:12]}

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

    return {"matches": matches, "match_count": len(matches), "interpretation": "relevant_for_review" if matches else "no_specific_match"}
