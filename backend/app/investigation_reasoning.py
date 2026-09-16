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
Correlation is association, never proof of causation. If evidence is insufficient, say so explicitly.
Do not recommend changing DCS/PLC/SIS setpoints, valves, controller parameters or closed-loop controls.
Process access is read-only. If data_quality is SIMULATED, prominently state that this is a development demonstration, not an operational plant conclusion.
Respond in the same language as the user's goal."""


def _history_payload(item: dict[str, Any]) -> Any:
    data = item.get("data")
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def build_deterministic_analytics(synthesis: dict[str, Any]) -> dict[str, Any]:
    histories = [item for item in synthesis.get("evidence_package", []) if item.get("tool") == "get_history"]
    summaries: dict[str, Any] = {}
    deviations: dict[str, Any] = {}
    series: list[tuple[str, Any]] = []
    for item in histories:
        evidence_id = str(item.get("evidence_id", "history"))
        payload = _history_payload(item)
        summaries[evidence_id] = summarize_series(payload)
        deviations[evidence_id] = detect_deviation(payload)
        series.append((evidence_id, payload))
    correlations = []
    for (left_id, left), (right_id, right) in combinations(series, 2):
        result = pearson(left, right)
        correlations.append({"left": left_id, "right": right_id, **result})
    return {"summaries": summaries, "deviations": deviations, "correlations": correlations}


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
    # Raw historian arrays can contain thousands of samples per tag. They have already
    # been reduced deterministically above, so never send those arrays into the LLM.
    # This keeps the reasoning prompt comfortably inside small embedded-model contexts.
    discovery = [_compact_discovery(item) for item in synthesis.get("discovery_evidence", []) if isinstance(item, dict)]
    return {
        "goal": goal,
        "data_source": {key: data_source.get(key) for key in ("mode", "data_quality", "source", "process_writes") if key in data_source},
        "time_window": synthesis.get("time_window"),
        "resolved_tags": synthesis.get("resolved_tags", []),
        "deterministic_analytics": analytics,
        "discovery_evidence": discovery,
        "history_evidence_ids": [item.get("evidence_id") for item in synthesis.get("evidence_package", []) if isinstance(item, dict) and item.get("tool") == "get_history"],
        "limitations": synthesis.get("limitations", []),
    }


async def reason_about_investigation(*, goal: str, synthesis: dict[str, Any], data_source: dict[str, Any]) -> dict[str, Any]:
    analytics = build_deterministic_analytics(synthesis)
    if not synthesis.get("ready_for_reasoning"):
        return {"available": False, "model": None, "text": "Insufficient source-grounded evidence for engineering reasoning.", "analytics": analytics}
    context = _reasoning_context(goal=goal, synthesis=synthesis, data_source=data_source, analytics=analytics)
    try:
        response = await LocalAIClient().generate(
            "Produce a concise evidence-grounded engineering assessment. Focus on the strongest observations, associations, plausible hypotheses, recommended read-only checks and limitations.",
            context,
            system_prompt=INVESTIGATION_SYSTEM_PROMPT,
            temperature=0.05,
        )
        return {"available": True, "model": response.model, "text": response.text, "analytics": analytics}
    except LocalAIError as exc:
        return {"available": False, "model": None, "text": f"Local reasoning model unavailable: {exc}", "analytics": analytics}
