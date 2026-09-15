"""Build auditable Markdown engineering reports from investigation evidence."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any


def build_investigation_report(*, goal: str, unit_key: str, synthesis: dict[str, Any], conclusion: str | None = None) -> str:
    evidence = synthesis.get("evidence_package") or []
    discovery = synthesis.get("discovery_evidence") or []
    limitations = synthesis.get("limitations") or []
    lines = [f"# Engineering Investigation — {unit_key.upper()}", "", f"**Goal:** {goal}",
             f"**Generated:** {datetime.now(timezone.utc).isoformat()}", "", "## Conclusion", ""]
    lines.append(conclusion.strip() if conclusion and conclusion.strip() else "No causal conclusion has been approved from the available evidence yet.")
    lines += ["", "## Evidence", ""]
    all_evidence = list(discovery) + list(evidence)
    if not all_evidence: lines.append("No source-grounded evidence was available.")
    for item in all_evidence:
        eid = item.get("evidence_id") or f"{item.get('tool','source')}:{item.get('step_id','?')}"
        provenance = item.get("provenance") or {}
        lines.append(f"- **{eid}** — source/provenance: `{provenance}`")
    lines += ["", "## Limitations", ""]
    if limitations:
        lines.extend(f"- {item}" for item in limitations)
    else: lines.append("- None recorded by the execution layer.")
    lines += ["", "## Safety boundary", "", "This investigation is analytical and read-only toward process-control systems. It does not change DCS/PLC/SIS setpoints, valves or controller parameters.", ""]
    return "\n".join(lines)
