from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from .local_ai import LocalAIClient, LocalAIError
from .site_model import ProcessUnit, SiteModel, UnitTag


@dataclass(frozen=True)
class AgentResult:
    plan: dict[str, object]
    message: str


_AGENT_SYSTEM = """You are the natural-language control brain for a refinery engineering dashboard.
You understand conversational Greek and English, including corrections, ellipsis and references such as
'αυτό', 'εκεί', 'το προηγούμενο', 'που βάλαμε', 'έκανες λάθος'. You NEVER invent units, tags or widget ids.
You do not directly control the plant; dashboard operations are read-only visualization operations.

Return ONLY one JSON object, no markdown, with this schema:
{
  "action": "add|remove|remove_all|move|answer|clarify",
  "unit": "canonical unit key or null",
  "metric": "semantic metric/tag phrase or null",
  "reference": "last|all|widget id|description|null",
  "widget_type": "trend|kpi|average|summary|null",
  "period": "8h or another concise period|null",
  "answer": "natural Greek response or clarification"
}

Rules:
- Explicit unit spoken by the user always wins over current/previous context.
- For corrections, infer the intended target from conversation state and current widgets.
- 'γράφημα/διάγραμμα/chart/trend' means trend unless context clearly says otherwise.
- 'όλα τα γραφήματα' means remove_all, never remove one.
- If the user asks a question, use answer and answer from supplied state only.
- If a required unit/metric/reference is genuinely ambiguous, use clarify instead of guessing.
- Use canonical unit keys exactly as supplied in AVAILABLE UNITS.
- Prefer semantic metric names from AVAILABLE METRICS.
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("agent returned no JSON object")
    payload = json.loads(raw[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("agent response must be an object")
    return payload


def _catalog(site: SiteModel) -> list[dict[str, object]]:
    return [
        {
            "key": unit.key,
            "name": unit.name,
            "aliases": list(unit.aliases),
            "metrics": [
                {"key": tag.key, "label": tag.label, "semantic": tag.semantic, "aliases": list(tag.aliases)}
                for tag in unit.tags
            ],
        }
        for unit in site.units
    ]


def _find_unit(site: SiteModel, value: object) -> ProcessUnit | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return site.find_unit(value.strip())


def _find_tag(unit: ProcessUnit, query: object) -> UnitTag | None:
    if not isinstance(query, str) or not query.strip():
        return None
    needle = query.strip().casefold()
    exact: list[UnitTag] = []
    partial: list[UnitTag] = []
    for tag in unit.tags:
        candidates = [tag.key, tag.label, tag.semantic, *tag.aliases]
        folded = [value.casefold() for value in candidates if value]
        if needle in folded:
            exact.append(tag)
        elif any(needle in value or value in needle for value in folded):
            partial.append(tag)
    if len(exact) == 1:
        return exact[0]
    if not exact and len(partial) == 1:
        return partial[0]
    return None


def _widget_for(unit: ProcessUnit, tag: UnitTag, widget_type: str, period: str, order: int) -> dict[str, object]:
    kind = widget_type if widget_type in {"trend", "kpi", "average"} else "trend"
    width, height = (12, "tall") if kind == "trend" else (4, "compact")
    return {
        "id": f"{unit.key}-{tag.key}-{uuid.uuid4().hex[:8]}",
        "type": kind,
        "title": tag.label,
        "unit_key": unit.key,
        "tag_keys": [tag.key],
        "period": period or "8h",
        "layout": {"order": order, "width": width, "height": height},
    }


def _last_widget(state: dict[str, object], widgets: list[dict[str, object]]) -> dict[str, object] | None:
    candidate = state.get("last_widget")
    if isinstance(candidate, dict):
        candidate_id = str(candidate.get("id", ""))
        for widget in widgets:
            if str(widget.get("id", "")) == candidate_id:
                return widget
        # A correction can refer to a widget that was created in the last turn even if state
        # was persisted before a UI refresh. Match semantic identity as a safe fallback.
        unit_key = str(candidate.get("unit_key", ""))
        tags = candidate.get("tag_keys")
        for widget in reversed(widgets):
            if str(widget.get("unit_key", "")) == unit_key and widget.get("tag_keys") == tags:
                return widget
    return widgets[-1] if len(widgets) == 1 else None


def _match_reference(reference: object, metric: object, unit: ProcessUnit | None, widgets: list[dict[str, object]], state: dict[str, object]) -> list[dict[str, object]]:
    if reference == "last":
        last = _last_widget(state, widgets)
        return [last] if last else []
    ref = str(reference or "").casefold()
    metric_text = str(metric or "").casefold()
    matches: list[dict[str, object]] = []
    for widget in widgets:
        if unit and str(widget.get("unit_key", "")).casefold() != unit.key.casefold():
            continue
        haystack = " ".join([str(widget.get("id", "")), str(widget.get("title", "")), *(str(x) for x in (widget.get("tag_keys") or []))]).casefold()
        if (ref and ref not in {"all", "null"} and ref in haystack) or (metric_text and metric_text in haystack):
            matches.append(widget)
    return matches


async def plan_with_local_agent(command: str, site: SiteModel, state: dict[str, object], widgets: list[dict[str, object]]) -> AgentResult | None:
    """Use the bundled local LLM for language understanding; compile its intent deterministically.

    The model never emits executable dashboard objects. It emits semantic intent only; this function
    resolves that intent against the real local unit/tag/widget catalog before producing a plan.
    """
    context = {
        "available_units": _catalog(site),
        "conversation_state": state,
        "current_widgets": widgets,
        "user_command": command,
    }
    try:
        response = await LocalAIClient().generate(
            f"{_AGENT_SYSTEM}\n\nInterpret USER COMMAND using the supplied local state. USER COMMAND: {command}",
            context=context,
        )
        intent = _extract_json(response.text)
    except (LocalAIError, ValueError, json.JSONDecodeError):
        return None

    action = str(intent.get("action") or "clarify").casefold()
    message = str(intent.get("answer") or "").strip()
    unit = _find_unit(site, intent.get("unit"))
    widget_type = str(intent.get("widget_type") or "trend").casefold()
    period = str(intent.get("period") or "8h")

    if action in {"answer", "clarify"}:
        if not message:
            message = "Χρειάζομαι μια μικρή διευκρίνιση για να το κάνω σωστά." if action == "clarify" else ""
        return AgentResult({"action": action, "read_only": True, "requires_confirmation": False, "needs_clarification": action == "clarify"}, message)

    if action == "add":
        if unit is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, "Σε ποια μονάδα θέλεις να το βάλω;")
        tag = _find_tag(unit, intent.get("metric"))
        if tag is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, f"Ποια ακριβώς μέτρηση θέλεις στη μονάδα {unit.name};")
        widget = _widget_for(unit, tag, widget_type, period, len(widgets))
        return AgentResult({"action": "add_widget", "widget": widget, "read_only": True, "requires_confirmation": False}, message or f"Έβαλα το {tag.label} στη μονάδα {unit.name}.")

    if action == "remove_all":
        candidates = [w for w in widgets if (unit is None or str(w.get("unit_key", "")).casefold() == unit.key.casefold()) and str(w.get("type", "")).casefold() == "trend"]
        ids = [str(w.get("id")) for w in candidates if w.get("id")]
        if not ids:
            return AgentResult({"action": "answer", "read_only": True}, message or "Δεν υπάρχουν γραφήματα για αφαίρεση.")
        return AgentResult({"action": "remove_widgets", "target_ids": ids, "read_only": True, "requires_confirmation": False}, message or f"Αφαίρεσα {len(ids)} γραφήματα.")

    if action in {"remove", "move"}:
        matches = _match_reference(intent.get("reference"), intent.get("metric"), None if action == "move" else unit, widgets, state)
        if len(matches) != 1:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, message or "Ποιο ακριβώς γράφημα εννοείς;")
        target = matches[0]
        if action == "remove":
            return AgentResult({"action": "remove_widget", "target_id": str(target.get("id")), "read_only": True, "requires_confirmation": False}, message or "Το αφαίρεσα.")
        if unit is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, "Σε ποια μονάδα θέλεις να το μεταφέρω;")
        old_unit = site.find_unit(str(target.get("unit_key", "")))
        old_tag = None
        tag_keys = target.get("tag_keys")
        if old_unit and isinstance(tag_keys, list) and tag_keys:
            old_tag = next((tag for tag in old_unit.tags if tag.key == str(tag_keys[0])), None)
        if old_tag is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, "Δεν μπορώ να ταυτοποιήσω με ασφάλεια τη μέτρηση του γραφήματος.")
        new_tag = unit.tag_by_semantic(old_tag.semantic)
        if new_tag is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, f"Δεν βρήκα αντίστοιχη μέτρηση {old_tag.label} στη μονάδα {unit.name}.")
        replacement = _widget_for(unit, new_tag, str(target.get("type", "trend")), str(target.get("period", "8h")), 0)
        return AgentResult({"action": "replace_widget", "target_id": str(target.get("id")), "widget": replacement, "read_only": True, "requires_confirmation": False}, message or f"Το μετέφερα στη μονάδα {unit.name}.")

    return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, message or "Δεν είμαι αρκετά βέβαιος για την ενέργεια. Πες μου το λίγο διαφορετικά.")
