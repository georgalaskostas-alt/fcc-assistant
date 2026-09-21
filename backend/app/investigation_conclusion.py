"""Deterministic evidence-aware conclusion for refinery investigations.

This module summarizes what the evidence supports without allowing an LLM to
manufacture confidence or turn association into causation.
"""
from __future__ import annotations
from typing import Any


def _confidence(*, support: int, contradictions: int, missing: int) -> dict[str, Any]:
    score = max(0, min(100, 35 + min(support, 3) * 15 - min(contradictions, 3) * 18 - min(missing, 3) * 8))
    if contradictions:
        level = "low"
    elif support >= 2 and missing == 0:
        level = "moderate"
    elif support >= 1:
        level = "limited"
    else:
        level = "insufficient"
    return {
        "level": level,
        "score": score,
        "basis": {
            "supporting_independent_evidence": support,
            "contradicting_independent_evidence": contradictions,
            "missing_evidence_items": missing,
        },
        "meaning": "Evidence sufficiency for this explanation; not probability of causation.",
    }


def build_evidence_aware_conclusion(*, analytics: dict[str, Any],
                                    hypotheses: list[dict[str, Any]],
                                    synthesis: dict[str, Any]) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    for tag, summary in (analytics.get("summaries") or {}).items():
        if not isinstance(summary, dict) or not summary.get("count"):
            continue
        facts.append({
            "tag_key": tag,
            "samples": int(summary.get("count") or 0),
            "mean": summary.get("mean"),
            "minimum": summary.get("min"),
            "maximum": summary.get("max"),
            "delta": summary.get("delta"),
            "evidence_ids": [summary.get("evidence_id")] if summary.get("evidence_id") else [],
        })

    supported: list[dict[str, Any]] = []
    contradicted: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue
        support = len(hypothesis.get("supporting_independent_evidence") or [])
        contradictions = len(hypothesis.get("contradicting_independent_evidence") or [])
        missing_items = list(hypothesis.get("missing_evidence") or [])
        item = {
            "hypothesis_id": hypothesis.get("id"),
            "statement": hypothesis.get("statement"),
            "evidence_status": hypothesis.get("evidence_status"),
            "causal_status": "not_established",
            "confidence": _confidence(support=support, contradictions=contradictions, missing=len(missing_items)),
            "supporting_evidence": list(hypothesis.get("supporting_independent_evidence") or []),
            "contradicting_evidence": list(hypothesis.get("contradicting_independent_evidence") or []),
            "missing_evidence": missing_items,
        }
        if contradictions and not support:
            contradicted.append(item)
        elif support and not contradictions:
            supported.append(item)
        else:
            unresolved.append(item)

    evidence_package = synthesis.get("evidence_package") if isinstance(synthesis.get("evidence_package"), list) else []
    sources = []
    for evidence in evidence_package:
        if not isinstance(evidence, dict):
            continue
        sources.append({
            "evidence_id": evidence.get("stable_evidence_id") or evidence.get("evidence_id"),
            "tool": evidence.get("tool"),
            "description": evidence.get("description"),
            "provenance": dict(evidence.get("provenance") or {}),
        })

    limitations = [str(value) for value in (synthesis.get("limitations") or [])]
    if not facts:
        limitations.append("No usable historian series were available for deterministic measured facts.")
    if not sources:
        limitations.append("No source-grounded evidence package was available.")

    return {
        "observed_facts": facts,
        "supported_explanations": supported,
        "contradicted_explanations": contradicted,
        "unresolved_explanations": unresolved,
        "limitations": list(dict.fromkeys(limitations)),
        "sources": sources,
        "overall_causal_conclusion": "not_established",
        "confidence_policy": "Deterministic evidence sufficiency only; never LLM self-confidence or probability of causation.",
        "process_control_actions_allowed": False,
    }
