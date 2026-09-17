"""Final deterministic gate for engineering narrative shown to users.

This is deliberately independent from the LLM prompt. If a generated narrative
crosses the evidence contract, the UI receives a deterministic claims-only
assessment instead of the generated prose.
"""
from __future__ import annotations

import re
from typing import Any

_MECHANISM = re.compile(r"\b(caus(?:e|ed|es|ing)|drove|driven|drives|explains?|responsible for|resulted in|led to|triggered|influenc(?:e|ed|es|ing)|linked to|suggests? (?:a )?(?:possible )?mechanism)\b", re.I)
_UNSUPPORTED_BASELINE = re.compile(r"\b(within (?:the )?.{0,35}variability|within normal|normal range|normal operating|expected range)\b", re.I)
_CONTROL_ACTION = re.compile(r"\b(change|adjust|increase|decrease|raise|lower|open|close|move|set)\b.{0,45}\b(setpoint|valve|controller|output|dcs|plc|sis)\b", re.I)
_SIGNIFICANCE = re.compile(r"\b(statistically significant|statistical significance|significant deviation(?:s)?)\b", re.I)
_UNIT_TOKEN = re.compile(r"(?<![A-Za-z])(bar(?:g|a)?|kpa|mpa|psi|°c|°f|degc|%)(?![A-Za-z])", re.I)


def validate_engineering_narrative(text: str, *, allowed_units: set[str] | None = None) -> dict[str, Any]:
    allowed = {item.casefold() for item in (allowed_units or set())}
    violations: list[dict[str, str]] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean: continue
        if _MECHANISM.search(clean): violations.append({"type": "unsupported_mechanism", "text": clean})
        if _UNSUPPORTED_BASELINE.search(clean): violations.append({"type": "unsupported_baseline", "text": clean})
        if _CONTROL_ACTION.search(clean): violations.append({"type": "process_control_action", "text": clean})
        if _SIGNIFICANCE.search(clean): violations.append({"type": "unsupported_statistical_significance", "text": clean})
        for match in _UNIT_TOKEN.finditer(clean):
            token = match.group(1).casefold()
            if token not in allowed:
                violations.append({"type": "ungrounded_engineering_unit", "text": clean})
                break
    return {"valid": not violations, "violations": violations}


def claims_only_text(claims: list[dict[str, Any]], *, simulated: bool) -> str:
    lines = ["Generated engineering narrative withheld because it exceeded the validated evidence contract.", "", "Validated evidence:"]
    for claim in claims:
        if not isinstance(claim, dict): continue
        refs = ", ".join(str(item) for item in claim.get("evidence_ids", []) if item)
        statement = str(claim.get("statement") or "").strip()
        if statement:
            lines.append(f"- {statement}" + (f" [{refs}]" if refs else ""))
    lines.extend(["", "No causal mechanism, operating baseline, engineering unit, or control action is asserted unless independently grounded by source evidence."])
    if simulated: lines.append("SIMULATED DEVELOPMENT DATA: this is not an operational plant conclusion.")
    return "\n".join(lines)
