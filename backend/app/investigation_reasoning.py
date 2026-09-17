"""Evidence-grounded engineering reasoning for autonomous investigations."""
from __future__ import annotations

from itertools import combinations
from typing import Any

from .local_ai import LocalAIClient, LocalAIError
from .process_analytics import detect_deviation, pearson, summarize_series

INVESTIGATION_SYSTEM_PROMPT = """You are the local refinery engineering reasoning layer.
Use ONLY the supplied investigation evidence and deterministic analytics.
Never invent measurements, alarms, limits, documents, causal mechanisms or plant events.
Separate: Observations, Deterministic analytics, Engineering hypotheses, Recommended checks, Limitations.
Cite supplied evidence IDs in square brackets for evidence-backed statements.
Correlation is association, never proof or evidence of causation. Never say a correlated variable caused, drove, explains, likely caused, likely drove, or is likely linked to another variable unless independent source evidence explicitly supports that causal statement. Use wording such as 'moved together', 'was associated with', or 'is a hypothesis requiring validation'.
Do not claim statistical significance unless a significance test and its result are explicitly supplied.
Do not infer that the event in the user's question occurred merely because the user asked about it; describe only measured changes present in evidence.
Do not recommend changing DCS/PLC/SIS setpoints, valves, controller parameters or closed-loop controls.
Process access is read-only. If data_quality is SIMULATED, prominently state that this is a development demonstration, not an operational plant conclusion.
Respond in the same language as the user's goal."""


def _history_payload(item: dict[str, Any]) -> Any:
    data = item.get("data")
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def _tag_from_history_item(item: dict[str, Any]) -> str | None:
    description = str(item.get("description") or "")
    marker = "historian evidence for "
    lowered = description.casefold()
    if marker in lowered:
        start = lowered.index(marker) + len(marker)
        return description[start:].strip().rstrip(".") or None
    provenance = item.get("provenance")
    if isinstance(provenance, dict):
        value = provenance.get("tag_key")
        if value: return str(value)
    return None


def build_deterministic_analytics(synthesis: dict[str, Any]) -> dict[str, Any]:
    histories = [item for item in synthesis.get("evidence_package", []) if item.get("tool") == "get_history"]
    summaries: dict[str, Any] = {}
    deviations: dict[str, Any] = {}
    series: list[tuple[str, str, Any]] = []
    evidence_labels: dict[str, str] = {}
    for item in histories:
        evidence_id = str(item.get("evidence_id", "history"))
        tag_key = _tag_from_history_item(item) or evidence_id
        evidence_labels[evidence_id] = tag_key
        payload = _history_payload(item)
        summaries[tag_key] = {"evidence_id": evidence_id, **summarize_series(payload)}
        deviations[tag_key] = {"evidence_id": evidence_id, **detect_deviation(payload)}
        series.append((evidence_id, tag_key, payload))
    correlations = []
    for (left_id, left_tag, left), (right_id, right_tag, right) in combinations(series, 2):
        result = pearson(left, right)
        correlations.append({"left": left_tag, "right": right_tag, "left_evidence_id": left_id, "right_evidence_id": right_id, **result})
    return {"evidence_labels": evidence_labels, "summaries": summaries, "deviations": deviations, "correlations": correlations}


def _compact_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    keep = ("source", "mode", "data_quality", "unit", "unit_key", "tag_key", "document_id", "revision", "page", "scope_kind", "scope_id")
    return {key: value[key] for key in keep if key in value}


def _compact_discovery(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data")
    compact_data: Any = None
    if item.get("tool") == "search_archive":
        rows = data.get("hits", data.get("items", [])) if isinstance(data, dict) else data
        if isinstance(rows, list):
            compact_data = []
            for row in rows[:6]:
                if not isinstance(row, dict): continue
                compact_data.append({key: row[key] for key in ("document_id", "title", "revision", "document_type", "page", "text", "score") if key in row})
    elif item.get("tool") == "search_tags":
        rows = data.get("hits", data.get("tags", [])) if isinstance(data, dict) else data
        if isinstance(rows, list):
            compact_data = [{key: row[key] for key in ("key", "tag_key", "name", "label", "semantic_key", "unit", "unit_key") if key in row} for row in rows[:8] if isinstance(row, dict)]
    return {"evidence_id": item.get("evidence_id"), "description": item.get("description"), "data": compact_data, "provenance": _compact_provenance(item.get("provenance"))}


def _reasoning_context(*, goal: str, synthesis: dict[str, Any], data_source: dict[str, Any], analytics: dict[str, Any]) -> dict[str, Any]:
    discovery = [_compact_discovery(item) for item in synthesis.get("discovery_evidence", []) if isinstance(item, dict)]
    return {
        "goal": goal,
        "data_source": {key: data_source.get(key) for key in ("mode", "data_quality", "source", "process_writes") if key in data_source},
        "time_window": synthesis.get("time_window"),
        "resolved_tags": synthesis.get("resolved_tags", []),
        "deterministic_analytics": analytics,
        "discovery_evidence": discovery,
        "limitations": synthesis.get("limitations", []),
    }


async def reason_about_investigation(*, goal: str, synthesis: dict[str, Any], data_source: dict[str, Any]) -> dict[str, Any]:
    analytics = build_deterministic_analytics(synthesis)
    if not synthesis.get("ready_for_reasoning"):
        return {"available": False, "model": None, "text": "Insufficient source-grounded evidence for engineering reasoning.", "analytics": analytics}
    context = _reasoning_context(goal=goal, synthesis=synthesis, data_source=data_source, analytics=analytics)
    try:
        response = await LocalAIClient().generate(
            "Produce a concise evidence-grounded engineering assessment. Report measured observations first. Treat correlations only as associations. Put possible mechanisms only under hypotheses and state what additional evidence would validate or reject each hypothesis.",
            context,
            system_prompt=INVESTIGATION_SYSTEM_PROMPT,
            temperature=0.05,
        )
        return {"available": True, "model": response.model, "text": response.text, "analytics": analytics}
    except LocalAIError as exc:
        return {"available": False, "model": None, "text": f"Local reasoning model unavailable: {exc}", "analytics": analytics}
