from __future__ import annotations

from dataclasses import asdict
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

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

    # Partial transcription exists only for responsive visual feedback. Keep its
    # prompt deliberately light so short clips are not biased toward a long list
    # of tags. The final pass is the authoritative command transcription.
    if normalized_mode == "partial":
        prompt = "Ελληνική ομιλία με πιθανές αγγλικές τεχνικές λέξεις και ακρωνύμια διυλιστηρίου."
    else:
        prompt_terms = list(dict.fromkeys([scope, *extra_terms]))[:24]
        prompt = (
            "Η ομιλία είναι στα Ελληνικά. Απόδωσε πιστά ολόκληρη την πρόταση στα Ελληνικά. "
            "Μην εφευρίσκεις λέξεις. Διατήρησε μόνο πραγματικούς τεχνικούς όρους, tags και "
            "ακρωνύμια όπως FCC, HCU και reaction temperature στην αγγλική γραφή τους. "
            "Πιθανοί όροι: " + ", ".join(prompt_terms)
        )

    try:
        data = await audio.read()
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio clip is too large")
        raw = transcribe_wav(data, prompt=prompt, high_accuracy=normalized_mode == "final")
        decision = normalize_transcript(raw, extra_terms=extra_terms)
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
