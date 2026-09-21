"""Reconcile autonomous follow-up tool results into structured investigation state."""
from __future__ import annotations
from typing import Any


def _successful_data(run: dict[str, Any], tool: str) -> list[Any]:
    executions = run.get("executions") if isinstance(run.get("executions"), list) else []
    rows = []
    for execution in executions:
        if not isinstance(execution, dict):
            continue
        step = execution.get("step") if isinstance(execution.get("step"), dict) else {}
        result = execution.get("result") if isinstance(execution.get("result"), dict) else {}
        if step.get("tool_name") != tool or execution.get("status") != "succeeded":
            continue
        data = result.get("data")
        if isinstance(data, list):
            rows.extend(data)
        elif data is not None:
            rows.append(data)
    return rows


def _dedupe(rows: list[Any], keys: tuple[str, ...]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for row in rows:
        if isinstance(row, dict):
            identity = next((str(row.get(key)) for key in keys if row.get(key) is not None), "")
            if not identity:
                identity = repr(sorted(row.items(), key=lambda item: str(item[0])))
        else:
            identity = repr(row)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    return result


def reconcile_follow_up(synthesis: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    archive = _successful_data(run, "search_archive")
    events = _successful_data(run, "search_alarms_events")
    episodes = _successful_data(run, "find_similar_episodes")
    tags = _successful_data(run, "search_tags")
    histories = _successful_data(run, "get_history")

    if archive:
        current = synthesis.get("archive_evidence") if isinstance(synthesis.get("archive_evidence"), dict) else {}
        items = _dedupe([*(current.get("items") or []), *archive], ("record_id", "document_id", "id"))
        current.update({"attempted": True, "items": items, "count": len(items), "approved_only": True})
        synthesis["archive_evidence"] = current
        synthesis["archive_evidence_useful"] = True

    if events:
        current = synthesis.get("event_evidence") if isinstance(synthesis.get("event_evidence"), dict) else {}
        items = _dedupe([*(current.get("items") or []), *events], ("event_id", "id"))
        current.update({"attempted": True, "items": items, "count": len(items), "run": run})
        synthesis["event_evidence"] = current

    if episodes:
        current = synthesis.get("similar_episodes") if isinstance(synthesis.get("similar_episodes"), dict) else {}
        items = _dedupe([*(current.get("items") or []), *episodes], ("episode_id", "id"))
        current.update({"attempted": True, "items": items, "count": len(items), "run": run})
        synthesis["similar_episodes"] = current

    if tags:
        current = synthesis.get("discovered_tags") if isinstance(synthesis.get("discovered_tags"), dict) else {}
        before = _dedupe(list(current.get("items") or []), ("key", "tag_key", "id"))
        items = _dedupe([*before, *tags], ("key", "tag_key", "id"))
        current.update({"attempted": True, "items": items, "count": len(items)})
        synthesis["discovered_tags"] = current
        resolved = {str(value) for value in (synthesis.get("resolved_tags") or [])}
        pending = []
        for row in items:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or row.get("tag_key") or "").strip()
            if key and key not in resolved:
                pending.append(key)
        synthesis["pending_history_tags"] = list(dict.fromkeys(pending))

    if histories:
        current = synthesis.get("history_evidence") if isinstance(synthesis.get("history_evidence"), dict) else {}
        items = _dedupe([*(current.get("items") or []), *histories], ("tag_key", "key", "id"))
        current.update({"attempted": True, "items": items, "count": len(items), "run": run})
        synthesis["history_evidence"] = current

    return {
        "archive_added": len(archive),
        "events_added": len(events),
        "episodes_added": len(episodes),
        "tags_added": len(tags),
        "histories_added": len(histories),
    }
