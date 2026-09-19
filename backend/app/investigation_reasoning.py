"""Evidence-grounded engineering reasoning for autonomous investigations."""
from __future__ import annotations

import re
from itertools import combinations
from typing import Any

from .local_ai import LocalAIClient, LocalAIError
from .investigation_hypotheses import build_hypothesis_candidates, investigation_stop_decision
from .process_analytics import detect_deviation, lagged_pearson, pearson, summarize_series, temporal_profile

INVESTIGATION_SYSTEM_PROMPT = """You are the local refinery engineering reasoning layer.
Use ONLY the supplied investigation evidence and deterministic analytics.
Never invent measurements, alarms, limits, documents, causal mechanisms or plant events.
Separate: Observations, Deterministic analytics, Engineering hypotheses, Recommended checks, Limitations.
Correlation is association, never proof or evidence of causation. Never say a correlated variable caused, drove, explains, likely caused, likely drove, or is likely linked to another variable unless independent source evidence explicitly supports that causal statement. Use wording such as 'moved together', 'was associated with', or 'is a hypothesis requiring validation'.
Do not claim statistical significance unless a significance test and its result are explicitly supplied.
Do not infer that the event in the user's question occurred merely because the user asked about it; describe only measured changes present in evidence.
Do not recommend changing DCS/PLC/SIS setpoints, valves, controller parameters or closed-loop controls.
Process access is read-only. If data_quality is SIMULATED, prominently state that this is a development demonstration, not an operational plant conclusion.
Respond in the same language as the user's goal."""

CAUSAL_PATTERNS = (
    re.compile(r"\b(caus(?:e|ed|es|ing)|drove|driven|drives|explains?|responsible for|resulted in|led to|triggered)\b", re.I),
    re.compile(r"\b(likely|probably|probably)\s+(?:caused|drove|explains?|triggered|led to)\b", re.I),
)
SIGNIFICANCE_PATTERN = re.compile(r"\b(statistically significant|statistical significance|significant deviation(?:s)?)\b", re.I)
CONTROL_ACTION_PATTERN = re.compile(r"\b(change|adjust|increase|decrease|raise|lower|open|close|move|set)\b.{0,45}\b(setpoint|valve|controller|output|dcs|plc|sis)\b", re.I)


def _history_payload(item: dict[str, Any]) -> Any:
    data = item.get("data")
    if isinstance(data, dict) and "data" in data: return data["data"]
    return data


def _tag_from_history_item(item: dict[str, Any]) -> str | None:
    description = str(item.get("description") or ""); lowered = description.casefold()
    for marker in ("historian evidence for ", "adaptive read-only historian evidence for "):
        if marker in lowered:
            start = lowered.index(marker) + len(marker); return description[start:].strip().rstrip(".") or None
    provenance = item.get("provenance")
    if isinstance(provenance, dict) and provenance.get("tag_key"): return str(provenance["tag_key"])
    return None


def _trend_points(payload: Any, *, max_points: int = 120) -> list[dict[str, Any]]:
    current = payload
    for _ in range(3):
        if not isinstance(current, dict): break
        nested = current.get("data")
        if isinstance(nested, (dict, list)): current = nested; continue
        break
    rows = current if isinstance(current, list) else next((current.get(key) for key in ("values", "Values", "items", "Items") if isinstance(current, dict) and isinstance(current.get(key), list)), [])
    points: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if isinstance(row, dict):
            value = row.get("value", row.get("Value")); timestamp = row.get("timestamp", row.get("Timestamp"))
            if isinstance(value, dict): value = value.get("Value", value.get("value"))
        else: value, timestamp = row, None
        if isinstance(value, bool): continue
        try: numeric = float(value)
        except (TypeError, ValueError): continue
        points.append({"x": str(timestamp) if timestamp is not None else str(index), "y": numeric})
    if len(points) <= max_points: return points
    stride = max(1, (len(points) - 1) // (max_points - 1)); sampled = points[::stride]
    if sampled[-1] != points[-1]: sampled.append(points[-1])
    return sampled[:max_points]


def build_deterministic_analytics(synthesis: dict[str, Any]) -> dict[str, Any]:
    histories = [item for item in synthesis.get("evidence_package", []) if item.get("tool") == "get_history"]
    summaries: dict[str, Any] = {}; deviations: dict[str, Any] = {}; temporal: dict[str, Any] = {}; trends: dict[str, Any] = {}; series: list[tuple[str, str, Any]] = []; evidence_labels: dict[str, str] = {}
    for item in histories:
        evidence_id = str(item.get("evidence_id", "history")); tag_key = _tag_from_history_item(item) or evidence_id; evidence_labels[evidence_id] = tag_key; payload = _history_payload(item)
        summaries[tag_key] = {"evidence_id": evidence_id, **summarize_series(payload)}; deviations[tag_key] = {"evidence_id": evidence_id, **detect_deviation(payload)}; temporal[tag_key] = {"evidence_id": evidence_id, **temporal_profile(payload)}; trends[tag_key] = {"evidence_id": evidence_id, "points": _trend_points(payload)}; series.append((evidence_id, tag_key, payload))
    correlations = []
    for (left_id, left_tag, left), (right_id, right_tag, right) in combinations(series, 2): correlations.append({"left": left_tag, "right": right_tag, "left_evidence_id": left_id, "right_evidence_id": right_id, **pearson(left, right), "lagged": lagged_pearson(left, right)})
    return {"evidence_labels": evidence_labels, "summaries": summaries, "deviations": deviations, "temporal": temporal, "correlations": correlations, "trends": trends}


def build_structured_claims(analytics: dict[str, Any], *, data_quality: str | None = None) -> list[dict[str, Any]]:
    """Create machine-checkable claims only from deterministic analytics.

    Mechanistic hypotheses are intentionally not manufactured here. A future
    hypothesis may be admitted only when its evidence/required-evidence contract
    is explicit and validated separately.
    """
    claims: list[dict[str, Any]] = []
    evidence_status = "simulated" if data_quality == "SIMULATED" else "measured"
    for tag, summary in analytics.get("summaries", {}).items():
        if not isinstance(summary, dict) or not summary.get("count"): continue
        evidence_id = str(summary.get("evidence_id") or "")
        start, end, delta = summary.get("first"), summary.get("last"), summary.get("delta")
        statement = f"{tag}: {summary.get('count')} samples; mean={summary.get('mean')}, min={summary.get('min')}, max={summary.get('max')}"
        if start is not None and end is not None: statement += f", first={start}, last={end}"
        if delta is not None: statement += f", delta={delta}"
        claims.append({"id": f"observation:{tag}", "type": "measured_fact", "statement": statement, "evidence_ids": [evidence_id] if evidence_id else [], "evidence_status": evidence_status, "confidence": "high", "required_evidence": []})
    for index, item in enumerate(analytics.get("correlations", [])):
        if not isinstance(item, dict) or item.get("r") is None: continue
        left, right, r = item.get("left"), item.get("right"), item.get("r")
        refs = [str(value) for value in (item.get("left_evidence_id"), item.get("right_evidence_id")) if value]
        claims.append({"id": f"association:{index}", "type": "association", "statement": f"{left} and {right} are associated in the analyzed window (Pearson r={r}); this does not establish causation.", "evidence_ids": refs, "evidence_status": evidence_status, "confidence": "high", "required_evidence": ["Independent process/event evidence is required before making a causal claim."]})
    return claims


def _compact_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict): return {}
    keep = ("source", "mode", "data_quality", "unit", "unit_key", "tag_key", "document_id", "revision", "page", "scope_kind", "scope_id")
    return {key: value[key] for key in keep if key in value}


def _compact_discovery(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data"); compact_data: Any = None
    if item.get("tool") == "search_archive":
        rows = data.get("hits", data.get("items", [])) if isinstance(data, dict) else data
        if isinstance(rows, list): compact_data = [{key: row[key] for key in ("document_id", "title", "revision", "document_type", "page", "text", "score") if key in row} for row in rows[:6] if isinstance(row, dict)]
    elif item.get("tool") == "search_tags":
        rows = data.get("hits", data.get("tags", [])) if isinstance(data, dict) else data
        if isinstance(rows, list): compact_data = [{key: row[key] for key in ("key", "tag_key", "name", "label", "semantic_key", "unit", "unit_key") if key in row} for row in rows[:8] if isinstance(row, dict)]
    return {"evidence_id": item.get("evidence_id"), "description": item.get("description"), "data": compact_data, "provenance": _compact_provenance(item.get("provenance"))}


def _reasoning_context(*, goal: str, synthesis: dict[str, Any], data_source: dict[str, Any], analytics: dict[str, Any]) -> dict[str, Any]:
    discovery = [_compact_discovery(item) for item in synthesis.get("discovery_evidence", []) if isinstance(item, dict)]; llm_analytics = {key: value for key, value in analytics.items() if key != "trends"}
    return {"goal": goal, "data_source": {key: data_source.get(key) for key in ("mode", "data_quality", "source", "process_writes") if key in data_source}, "time_window": synthesis.get("time_window"), "resolved_tags": synthesis.get("resolved_tags", []), "deterministic_analytics": llm_analytics, "discovery_evidence": discovery, "archive_evidence": synthesis.get("archive_evidence", {}), "event_evidence": synthesis.get("event_evidence", {}), "similar_episodes": synthesis.get("similar_episodes", {}), "limitations": synthesis.get("limitations", [])}


def validate_reasoning_text(text: str) -> dict[str, Any]:
    """Deterministic final gate: unsafe epistemic claims never reach the engineering UI."""
    violations: list[dict[str, str]] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean: continue
        if any(pattern.search(clean) for pattern in CAUSAL_PATTERNS): violations.append({"type": "unsupported_causality", "text": clean})
        if SIGNIFICANCE_PATTERN.search(clean): violations.append({"type": "unsupported_statistical_significance", "text": clean})
        if CONTROL_ACTION_PATTERN.search(clean): violations.append({"type": "process_control_action", "text": clean})
    return {"valid": not violations, "violations": violations}


def _validated_fallback(*, analytics: dict[str, Any], data_source: dict[str, Any]) -> str:
    summaries = analytics.get("summaries", {}); correlations = analytics.get("correlations", [])
    lines = ["Bounded engineering assessment: the model narrative was rejected by deterministic evidence validation, so only validated evidence is shown.", "", "Validated observations:"]
    for tag, summary in summaries.items():
        if not isinstance(summary, dict) or not summary.get("count"): continue
        lines.append(f"- {tag}: n={summary.get('count')}, mean={summary.get('mean')}, min={summary.get('min')}, max={summary.get('max')}, delta={summary.get('delta')} [{summary.get('evidence_id')}]")
    if correlations:
        lines.extend(["", "Validated associations (correlation is not causation):"])
        for item in correlations:
            if item.get("r") is not None: lines.append(f"- {item.get('left')} ↔ {item.get('right')}: Pearson r={item.get('r')} [{item.get('left_evidence_id')}, {item.get('right_evidence_id')}]")
    temporal = analytics.get("temporal", {})
    if temporal:
        lines.extend(["", "Validated temporal observations:"])
        for tag, item in temporal.items():
            if isinstance(item, dict) and item.get("available"):
                lines.append(f"- {tag}: {item.get('direction')}; early mean={item.get('early_mean')}, late mean={item.get('late_mean')}, onset sample={item.get('onset_index')} [{item.get('evidence_id')}]")
    lines.extend(["", "Causal conclusion: not established by the available evidence.", "Next evidence required: alarms/events, operating context, relevant approved technical-archive guidance, and additional process variables identified by the unit semantic model."])
    if data_source.get("data_quality") == "SIMULATED": lines.append("SIMULATED DEVELOPMENT DATA: this is not an operational plant conclusion.")
    return "\n".join(lines)


async def reason_about_investigation(*, goal: str, synthesis: dict[str, Any], data_source: dict[str, Any]) -> dict[str, Any]:
    analytics = build_deterministic_analytics(synthesis)
    claims = build_structured_claims(analytics, data_quality=str(data_source.get("data_quality") or ""))
    hypotheses = build_hypothesis_candidates(analytics)
    stop_decision = investigation_stop_decision(synthesis=synthesis, analytics=analytics, hypotheses=hypotheses)
    if not synthesis.get("ready_for_reasoning"): return {"available": False, "model": None, "text": "Insufficient source-grounded evidence for engineering reasoning.", "analytics": analytics, "claims": claims, "hypotheses": hypotheses, "stop_decision": stop_decision, "validation": {"valid": True, "violations": []}}
    context = _reasoning_context(goal=goal, synthesis=synthesis, data_source=data_source, analytics=analytics)
    try:
        response = await LocalAIClient().generate("Produce a concise evidence-grounded engineering assessment. Report measured observations first. Treat correlations only as associations. Put possible mechanisms only under hypotheses and state what additional evidence would validate or reject each hypothesis.", context, system_prompt=INVESTIGATION_SYSTEM_PROMPT, temperature=0.05)
        validation = validate_reasoning_text(response.text)
        if not validation["valid"]:
            return {"available": False, "model": response.model, "text": _validated_fallback(analytics=analytics, data_source=data_source), "analytics": analytics, "claims": claims, "hypotheses": hypotheses, "stop_decision": stop_decision, "validation": validation}
        return {"available": True, "model": response.model, "text": response.text, "analytics": analytics, "claims": claims, "hypotheses": hypotheses, "stop_decision": stop_decision, "validation": validation}
    except LocalAIError as exc:
        return {"available": False, "model": None, "text": f"Local reasoning model unavailable: {exc}", "analytics": analytics, "claims": claims, "hypotheses": hypotheses, "stop_decision": stop_decision, "validation": {"valid": True, "violations": []}}
