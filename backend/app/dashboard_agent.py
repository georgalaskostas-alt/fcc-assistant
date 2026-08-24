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


_AGENT_SYSTEM = """You are FCC Assistant: an exceptionally capable refinery dashboard copilot.
Behave like a competent human colleague, not a command parser. Understand natural conversational Greek,
English and mixed Greek/English engineering language. Track conversational continuity, corrections,
ellipsis, pronouns and implied references: 'αυτό', 'εκεί', 'το προηγούμενο', 'αυτό που βάλαμε',
'έκανες λάθος', 'όχι εκεί', 'βγάλτο', 'βάλτο στον hydrocracker', 'πού το έβαλες;', etc.

Your job is semantic understanding only. You NEVER invent units, tags, values, alarms or widget ids.
You never directly control plant equipment. Dashboard operations are read-only visualization operations.
Use AVAILABLE UNITS, AVAILABLE METRICS, CURRENT WIDGETS and CONVERSATION STATE as your working memory.

Return ONLY one JSON object, no markdown:
{
  "action": "add|remove|remove_all|move|answer|clarify",
  "unit": "canonical unit key or null",
  "metric": "semantic metric/tag phrase or null",
  "reference": "last|all|widget id|description|null",
  "widget_type": "trend|kpi|average|summary|null",
  "period": "8h or another concise period|null",
  "answer": "short natural Greek response"
}

Reasoning policy:
- Understand intent, not keywords. The user does not need to use a standard phrase.
- Explicit information in the newest utterance overrides older context.
- Preserve omitted information from the immediately relevant prior turn when humans naturally would.
- A correction such as 'όχι FCC, Hydrocracker' means repair the relevant previous action, not create an unrelated action.
- 'αυτό/το/εκείνο/που βάλαμε/τελευταίο/προηγούμενο' normally refers to the most recently discussed or changed widget.
- If the user says an action was wrong and gives the correct unit, prefer moving/replacing the erroneous last widget.
- If the user asks where something was placed, answer from CURRENT WIDGETS/CONVERSATION STATE; do not attempt a dashboard mutation.
- 'όλα τα γραφήματα' means remove_all. Scope it to an explicitly mentioned unit; otherwise all trend widgets.
- 'γράφημα/διάγραμμα/chart/trend' defaults to trend.
- Infer a metric only when there is exactly one defensible catalog match or the conversation already establishes it.
- Ask a clarification only when two or more materially different executable interpretations remain. Do NOT clarify merely because wording is informal.
- Never silently substitute FCC for Hydrocracker/HCU or any other unit. Explicit unit always wins.
- Use canonical unit keys exactly as supplied.
- Keep answer conversational and concise, as if speaking aloud to the operator.
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
    return [{"key": u.key, "name": u.name, "aliases": list(u.aliases), "metrics": [{"key": t.key, "label": t.label, "semantic": t.semantic, "aliases": list(t.aliases)} for t in u.tags]} for u in site.units]


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
        folded = [v.casefold() for v in candidates if v]
        if needle in folded:
            exact.append(tag)
        elif any(needle in v or v in needle for v in folded):
            partial.append(tag)
    if len(exact) == 1:
        return exact[0]
    if not exact and len(partial) == 1:
        return partial[0]
    return None


def _widget_for(unit: ProcessUnit, tag: UnitTag, widget_type: str, period: str, order: int) -> dict[str, object]:
    kind = widget_type if widget_type in {"trend", "kpi", "average"} else "trend"
    width, height = (12, "tall") if kind == "trend" else (4, "compact")
    return {"id": f"{unit.key}-{tag.key}-{uuid.uuid4().hex[:8]}", "type": kind, "title": tag.label, "unit_key": unit.key, "tag_keys": [tag.key], "period": period or "8h", "layout": {"order": order, "width": width, "height": height}}


def _last_widget(state: dict[str, object], widgets: list[dict[str, object]]) -> dict[str, object] | None:
    candidate = state.get("last_widget")
    if isinstance(candidate, dict):
        cid = str(candidate.get("id", ""))
        for w in widgets:
            if str(w.get("id", "")) == cid:
                return w
        unit_key, tags = str(candidate.get("unit_key", "")), candidate.get("tag_keys")
        for w in reversed(widgets):
            if str(w.get("unit_key", "")) == unit_key and w.get("tag_keys") == tags:
                return w
    # Human conversational reference normally means the newest dashboard object.
    return widgets[-1] if widgets else None


def _match_reference(reference: object, metric: object, unit: ProcessUnit | None, widgets: list[dict[str, object]], state: dict[str, object]) -> list[dict[str, object]]:
    ref = str(reference or "").casefold()
    if ref in {"last", "previous", "τελευταίο", "τελευταιο", "προηγούμενο", "προηγουμενο", "αυτό", "αυτο"}:
        last = _last_widget(state, widgets)
        return [last] if last else []
    metric_text = str(metric or "").casefold()
    matches: list[dict[str, object]] = []
    for w in widgets:
        if unit and str(w.get("unit_key", "")).casefold() != unit.key.casefold():
            continue
        haystack = " ".join([str(w.get("id", "")), str(w.get("title", "")), *(str(x) for x in (w.get("tag_keys") or []))]).casefold()
        if (ref and ref not in {"all", "null"} and ref in haystack) or (metric_text and metric_text in haystack):
            matches.append(w)
    if not matches and not metric_text and not ref:
        last = _last_widget(state, widgets)
        return [last] if last else []
    return matches


def _human_widget_description(widget: dict[str, object], site: SiteModel) -> str:
    unit = site.find_unit(str(widget.get("unit_key", "")))
    title = str(widget.get("title", "γράφημα"))
    return f"{title} στη μονάδα {unit.name if unit else widget.get('unit_key', '')}"


async def plan_with_local_agent(command: str, site: SiteModel, state: dict[str, object], widgets: list[dict[str, object]]) -> AgentResult | None:
    context = {"available_units": _catalog(site), "conversation_state": state, "current_widgets": widgets, "user_command": command}
    try:
        response = await LocalAIClient().generate(f"{_AGENT_SYSTEM}\n\nInterpret the newest USER COMMAND in context: {command}", context=context)
        intent = _extract_json(response.text)
    except (LocalAIError, ValueError, json.JSONDecodeError):
        return None

    action = str(intent.get("action") or "clarify").casefold()
    message = str(intent.get("answer") or "").strip()
    unit = _find_unit(site, intent.get("unit"))
    widget_type = str(intent.get("widget_type") or "trend").casefold()
    period = str(intent.get("period") or "8h")

    if action == "answer":
        if not message:
            last = _last_widget(state, widgets)
            message = f"Το τελευταίο είναι {_human_widget_description(last, site)}." if last else "Δεν υπάρχει ακόμη γράφημα στο dashboard."
        return AgentResult({"action": "answer", "read_only": True, "requires_confirmation": False}, message)
    if action == "clarify":
        return AgentResult({"action": "clarify", "read_only": True, "requires_confirmation": False, "needs_clarification": True}, message or "Πες μου μόνο ποιο από τα διαθέσιμα εννοείς και το αναλαμβάνω.")

    if action == "add":
        if unit is None:
            remembered = str(state.get("last_requested_unit_key") or state.get("last_unit_key") or "")
            unit = site.find_unit(remembered) if remembered else None
        if unit is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, "Σε ποια μονάδα το θέλεις;")
        tag = _find_tag(unit, intent.get("metric"))
        if tag is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, f"Ποια μέτρηση θέλεις στη {unit.name};")
        widget = _widget_for(unit, tag, widget_type, period, len(widgets))
        return AgentResult({"action": "add_widget", "widget": widget, "read_only": True, "requires_confirmation": False}, message or f"Έτοιμο. Έβαλα {tag.label} στη {unit.name}.")

    if action == "remove_all":
        candidates = [w for w in widgets if (unit is None or str(w.get("unit_key", "")).casefold() == unit.key.casefold()) and str(w.get("type", "")).casefold() == "trend"]
        ids = [str(w.get("id")) for w in candidates if w.get("id")]
        if not ids:
            return AgentResult({"action": "answer", "read_only": True}, message or "Δεν έχει μείνει κάποιο γράφημα για αφαίρεση.")
        return AgentResult({"action": "remove_widgets", "target_ids": ids, "read_only": True, "requires_confirmation": False}, message or f"Έτοιμο. Αφαίρεσα και τα {len(ids)} γραφήματα.")

    if action in {"remove", "move"}:
        matches = _match_reference(intent.get("reference"), intent.get("metric"), None if action == "move" else unit, widgets, state)
        if len(matches) != 1:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, message or "Βλέπω περισσότερες από μία πιθανές επιλογές. Ποιο γράφημα εννοείς;")
        target = matches[0]
        if action == "remove":
            return AgentResult({"action": "remove_widget", "target_id": str(target.get("id")), "read_only": True, "requires_confirmation": False}, message or "Έγινε, το αφαίρεσα.")
        if unit is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, "Σε ποια μονάδα να το μεταφέρω;")
        old_unit = site.find_unit(str(target.get("unit_key", "")))
        tags = target.get("tag_keys")
        old_tag = next((t for t in old_unit.tags if isinstance(tags, list) and tags and t.key == str(tags[0])), None) if old_unit else None
        if old_tag is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, "Δεν μπορώ να ταυτοποιήσω με ασφάλεια τη μέτρηση αυτού του γραφήματος.")
        new_tag = unit.tag_by_semantic(old_tag.semantic)
        if new_tag is None:
            return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, f"Η {unit.name} δεν έχει αντιστοιχισμένη μέτρηση για {old_tag.label}.")
        replacement = _widget_for(unit, new_tag, str(target.get("type", "trend")), str(target.get("period", "8h")), 0)
        return AgentResult({"action": "replace_widget", "target_id": str(target.get("id")), "widget": replacement, "read_only": True, "requires_confirmation": False}, message or f"Σωστά. Το μετέφερα στη {unit.name}.")

    return AgentResult({"action": "clarify", "read_only": True, "needs_clarification": True}, message or "Δεν έχω αρκετή βεβαιότητα για να αλλάξω κάτι λάθος. Πες μου ποιο αντικείμενο εννοείς.")
