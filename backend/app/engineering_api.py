"""Opt-in, read-only endpoint for evidence-grounded FCC explanations.

This route does not modify setpoints, write plant data, or turn draft
benchmark cards into approved sources.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from .engineering_grounding import generate_grounded
from .engineering_knowledge import KnowledgeValidationError
from .local_ai import LocalAIClient, LocalAIError

router = APIRouter(prefix="/api/v1/ai/engineering", tags=["engineering"])


class EngineeringAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    topic: str = Field(min_length=1, max_length=128)

    @field_validator("question", "topic")
    @classmethod
    def reject_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()


@router.post("/ask")
async def engineering_ask(request: EngineeringAskRequest) -> dict[str, object]:
    """Respond using approved registry records only; never expose raw errors."""
    try:
        result = await generate_grounded(
            client=LocalAIClient(),
            question=request.question,
            topic=request.topic,
        )
    except (KnowledgeValidationError, OSError, ValueError) as exc:
        # Invalid or unreadable registry is a service error, not an empty registry.
        raise HTTPException(status_code=503, detail="Engineering evidence registry unavailable or invalid") from exc
    except LocalAIError as exc:
        raise HTTPException(status_code=502, detail="Local AI generation failed") from exc

    return {
        "mode": "approved_evidence_only",
        "read_only": True,
        "topic": request.topic,
        "status": "citation_screen_pass" if result["grounded"] else "insufficient_evidence",
        "answer": result["answer"],
        "sources": result["sources"],
        "model_invoked": result["model_invoked"],
        "validation": result.get("validation", "no_approved_evidence_or_citation_screen_failed"),
        "engineer_review_required": True,
    }
