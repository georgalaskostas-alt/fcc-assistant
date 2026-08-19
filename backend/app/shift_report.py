from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .analytics import AnalyticsError, summarize_pi_payload
from .tag_service import TagService, TagServiceError


class ShiftReportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShiftTagResult:
    key: str
    name: str
    group: str
    unit: str | None
    summary: dict[str, Any]


class ShiftReportEngine:
    """Builds a read-only engineering summary for one operating shift."""

    def __init__(self, service: TagService | None = None) -> None:
        self.service = service or TagService()

    async def generate(
        self,
        start_time: str,
        end_time: str,
        tag_keys: list[str] | None = None,
        max_count: int = 1000,
    ) -> dict[str, Any]:
        configured = self.service.registry.list()
        selected = configured if not tag_keys else [
            tag for tag in configured if tag.key in set(tag_keys)
        ]

        if tag_keys:
            found = {tag.key for tag in selected}
            missing = [key for key in tag_keys if key not in found]
            if missing:
                raise ShiftReportError(f"Unknown tag keys: {', '.join(missing)}")

        if not selected:
            raise ShiftReportError("No FCC tags are configured for this report")

        results: list[ShiftTagResult] = []
        errors: list[dict[str, str]] = []

        for tag in selected:
            try:
                payload = await self.service.recorded_values(
                    key=tag.key,
                    start_time=start_time,
                    end_time=end_time,
                    max_count=max_count,
                )
                # TagService wraps the raw PI response under the data key.
                summary = summarize_pi_payload(payload["data"])
                results.append(
                    ShiftTagResult(
                        key=tag.key,
                        name=tag.name,
                        group=tag.group,
                        unit=tag.unit,
                        summary=asdict(summary),
                    )
                )
            except (TagServiceError, AnalyticsError, KeyError) as exc:
                errors.append({"tag": tag.key, "error": str(exc)})

        groups: dict[str, list[dict[str, Any]]] = {}
        for result in results:
            groups.setdefault(result.group, []).append(asdict(result))

        return {
            "report_type": "shift",
            "read_only": True,
            "range": {"start_time": start_time, "end_time": end_time},
            "requested_tags": len(selected),
            "successful_tags": len(results),
            "failed_tags": len(errors),
            "groups": groups,
            "errors": errors,
        }
