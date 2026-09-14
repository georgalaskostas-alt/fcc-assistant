"""Platform tool adapters for the refinery AI assistant.

These adapters expose existing deterministic services through the generic tool
registry. They intentionally exclude process-control write actions and human
approval actions.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .agent_tools import ToolDefinition, ToolEffect, ToolParameter, ToolRegistry
from .document_registry import DocumentType
from .engineering_document_service import EngineeringDocumentService
from .engineering_documents import RedlineInstruction
from .refinery_model import DataDomain
from .tag_service import TagService
from .technical_archive import TechnicalArchive


def build_refinery_tool_registry(
    *,
    tag_service: TagService | None = None,
    archive: TechnicalArchive | None = None,
    engineering_documents: EngineeringDocumentService | None = None,
) -> ToolRegistry:
    tags = tag_service or TagService()
    technical_archive = archive or TechnicalArchive()
    document_service = engineering_documents or EngineeringDocumentService(
        registry=technical_archive.registry
    )
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="search_tags",
            description="Search configured historian tags by engineering name or alias.",
            domain=DataDomain.PROCESS,
            effect=ToolEffect.READ_ONLY,
            parameters=(ToolParameter("query", "string"),),
        ),
        lambda _context, args: tags.search(str(args["query"])),
    )

    async def get_history(_context, args: dict[str, Any]) -> dict[str, Any]:
        return await tags.recorded_values(
            key=str(args["tag_key"]),
            start_time=str(args["start_time"]),
            end_time=str(args["end_time"]),
            max_count=int(args.get("max_count", 1000)),
        )

    registry.register(
        ToolDefinition(
            name="get_history",
            description="Retrieve read-only recorded historian values for one approved tag.",
            domain=DataDomain.PROCESS,
            effect=ToolEffect.READ_ONLY,
            parameters=(
                ToolParameter("tag_key", "string"),
                ToolParameter("start_time", "string"),
                ToolParameter("end_time", "string"),
                ToolParameter("max_count", "integer", required=False),
            ),
        ),
        get_history,
    )

    def search_archive(_context, args: dict[str, Any]) -> list[dict[str, Any]]:
        raw_type = args.get("document_type")
        document_type = DocumentType(str(raw_type)) if raw_type else None
        hits = technical_archive.search(
            query=str(args["query"]),
            unit_key=str(args["unit_key"]),
            limit=int(args.get("limit", 8)),
            approved_only=bool(args.get("approved_only", True)),
            document_type=document_type,
            equipment_key=str(args["equipment_key"]) if args.get("equipment_key") else None,
        )
        return [asdict(hit) for hit in hits]

    registry.register(
        ToolDefinition(
            name="search_archive",
            description="Search revision-aware technical archive content with source provenance.",
            domain=DataDomain.KNOWLEDGE,
            effect=ToolEffect.READ_ONLY,
            parameters=(
                ToolParameter("query", "string"),
                ToolParameter("unit_key", "string"),
                ToolParameter("limit", "integer", required=False),
                ToolParameter("approved_only", "boolean", required=False),
                ToolParameter("document_type", "string", required=False),
                ToolParameter("equipment_key", "string", required=False),
            ),
        ),
        search_archive,
    )

    registry.register(
        ToolDefinition(
            name="get_document_context",
            description="Return identity, revision, approval state and provenance for one archive record.",
            domain=DataDomain.KNOWLEDGE,
            effect=ToolEffect.READ_ONLY,
            parameters=(ToolParameter("record_id", "string"),),
        ),
        lambda _context, args: technical_archive.document_context(str(args["record_id"])),
    )

    def find_approved_document(_context, args: dict[str, Any]) -> dict[str, Any]:
        record = document_service.approved_master(str(args["document_id"]))
        return record.to_dict()

    registry.register(
        ToolDefinition(
            name="find_approved_document",
            description="Resolve the current approved master revision for a controlled engineering document.",
            domain=DataDomain.KNOWLEDGE,
            effect=ToolEffect.READ_ONLY,
            parameters=(ToolParameter("document_id", "string"),),
        ),
        find_approved_document,
    )

    def propose_document_change(context, args: dict[str, Any]) -> dict[str, Any]:
        raw_instructions = args["instructions"]
        if not isinstance(raw_instructions, list) or not raw_instructions:
            raise ValueError("instructions must be a non-empty list")
        instructions: list[RedlineInstruction] = []
        for item in raw_instructions:
            if not isinstance(item, dict):
                raise ValueError("each redline instruction must be an object")
            instructions.append(
                RedlineInstruction(
                    description=str(item.get("description") or "").strip(),
                    page=int(item["page"]) if item.get("page") is not None else None,
                    target_reference=str(item["target_reference"]) if item.get("target_reference") else None,
                    markup_kind=str(item.get("markup_kind") or "note"),
                    metadata={str(k): str(v) for k, v in (item.get("metadata") or {}).items()},
                )
            )
        if any(not instruction.description for instruction in instructions):
            raise ValueError("each redline instruction requires a description")

        change = document_service.propose_against_approved(
            document_id=str(args["document_id"]),
            requested_by=context.actor_id,
            reason=str(args["reason"]),
            instructions=instructions,
            proposed_revision=str(args["proposed_revision"]),
        )
        return change.to_dict()

    registry.register(
        ToolDefinition(
            name="propose_document_change",
            description=(
                "Create a non-destructive proposed engineering-document change against the current approved master. "
                "This tool cannot approve or promote a revision."
            ),
            domain=DataDomain.KNOWLEDGE,
            effect=ToolEffect.CONTROLLED_DOCUMENT_PROPOSAL,
            parameters=(
                ToolParameter("document_id", "string"),
                ToolParameter("reason", "string"),
                ToolParameter("proposed_revision", "string"),
                ToolParameter("instructions", "array"),
            ),
        ),
        propose_document_change,
    )

    return registry
