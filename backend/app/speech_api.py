from __future__ import annotations

from dataclasses import asdict
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .dashboard_dialogue import DashboardDialogueStore
from .site_model import load_site_model
from .speech_domain import normalize_transcript
from .speech_runtime import SpeechRuntimeError, runtime_status, transcribe_wav

router = APIRouter(prefix="/api/v1/speech", tags=["local-speech"])


@router.get("/status")
def speech_status() -> dict[str, object]:
    status = runtime_status()
    return {
        **asdict(status),
        "engine": "whisper.cpp",
        "cloud": False,
        "audio_leaves_device": False,
        "confidence_semantics": "command confidence after domain normalization; not acoustic posterior probability",
    }


def _unit_vocabulary() -> list[str]:
    """Return a compact, local refinery-unit vocabulary for STT biasing.

    Unit names are more important than the full tag catalog for phrases such as
    "στο Hydrocracker". Learned aliases are included so explicit engineer
    corrections improve future recognition without sending anything off-device.
    """
    try:
        site = load_site_model()
    except (ValueError, OSError):
        return ["FCC", "HCU", "Hydrocracker"]

    terms: list[str] = []
    for unit in site.units:
        terms.extend([unit.key, unit.name, *getattr(unit, "aliases", ())])
    terms.extend(DashboardDialogueStore().aliases().keys())
    return list(dict.fromkeys(term.strip() for term in terms if term.strip()))[:24]


@router.post("/transcribe")
async def speech_transcribe(
    audio: UploadFile = File(...),
    scope: str = Form(default="all"),
    terms_json: str = Form(default="[]"),
    mode: str = Form(default="final"),
) -> dict[str, object]:
    try:
        parsed = json.loads(terms_json)
        extra_terms = [str(value) for value in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        extra_terms = []

    normalized_mode = mode.strip().casefold()
    if normalized_mode not in {"partial", "final"}:
        normalized_mode = "final"

    unit_terms = _unit_vocabulary()

    # Partial transcription exists only for responsive visual feedback. Unit
    # names are still supplied because confusing Hydrocracker/HCU with FCC is a
    # materially different command, while the long tag catalog remains omitted.
    if normalized_mode == "partial":
        prompt = (
            "Ελληνική ομιλία με πιθανές αγγλικές τεχνικές λέξεις. "
            "Άκουσε ιδιαίτερα προσεκτικά τα ονόματα μονάδων: "
            + ", ".join(unit_terms)
            + "."
        )
    else:
        domain_terms = list(dict.fromkeys([*unit_terms, scope, *extra_terms]))[:32]
        prompt = (
            "Η ομιλία είναι στα Ελληνικά. Απόδωσε πιστά ολόκληρη την πρόταση στα Ελληνικά. "
            "Μην αντικαθιστάς μία μονάδα με άλλη και μην εφευρίσκεις λέξεις. "
            "Διατήρησε τεχνικούς όρους, tags και ακρωνύμια όπως FCC, HCU, Hydrocracker και "
            "reaction temperature στην καθιερωμένη γραφή τους. Πιθανοί όροι: "
            + ", ".join(domain_terms)
        )

    try:
        data = await audio.read()
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio clip is too large")
        raw = transcribe_wav(data, prompt=prompt, high_accuracy=normalized_mode == "final")
        decision = normalize_transcript(raw, extra_terms=list(dict.fromkeys([*unit_terms, *extra_terms])))
    except SpeechRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await audio.close()

    return {
        "raw_text": decision.raw_text,
        "text": decision.normalized_text,
        "confidence": decision.confidence,
        "confidence_level": decision.level,
        "execute_immediately": decision.execute_immediately,
        "corrections": [asdict(item) for item in decision.corrections],
        "scope": scope,
        "language": "el",
        "engine": "whisper.cpp",
        "mode": normalized_mode,
        "local_only": True,
        "audio_retained": False,
    }
