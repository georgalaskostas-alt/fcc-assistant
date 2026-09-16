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
Every observation or hypothesis must cite one or more supplied evidence IDs in square brackets.
Correlation is association, never proof of causation.
If evidence is insufficient, say so explicitly.
Do not recommend changing DCS/PLC/SIS setpoints, valves, controller parameters or closed-loop controls.
Process access is read-only. If data_quality is SIMULATED, prominently state that the conclusion is a development demonstration and not an operational plant conclusion.
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


async def reason_about_investigation(*, goal: str, synthesis: dict[str, Any], data_source: dict[str, Any]) -> dict[str, Any]:
    analytics = build_deterministic_analytics(synthesis)
    if not synthesis.get("ready_for_reasoning"):
        return {"available": False, "model": None, "text": "Insufficient source-grounded evidence for engineering reasoning.", "analytics": analytics}
    context = {
        "goal": goal,
        "data_source": data_source,
        "time_window": synthesis.get("time_window"),
        "resolved_tags": synthesis.get("resolved_tags", []),
        "deterministic_analytics": analytics,
        "evidence": [
            {"evidence_id": item.get("evidence_id"), "description": item.get("description"), "data": item.get("data"), "provenance": item.get("provenance")}
            for item in [*synthesis.get("discovery_evidence", []), *synthesis.get("evidence_package", [])]
        ],
        "limitations": synthesis.get("limitations", []),
    }
    try:
        response = await LocalAIClient().generate(
            "Analyze this engineering investigation and produce a concise evidence-grounded engineering assessment.",
            context,
            system_prompt=INVESTIGATION_SYSTEM_PROMPT,
            temperature=0.05,
        )
        return {"available": True, "model": response.model, "text": response.text, "analytics": analytics}
    except LocalAIError as exc:
        return {"available": False, "model": None, "text": f"Local reasoning model unavailable: {exc}", "analytics": analytics}
