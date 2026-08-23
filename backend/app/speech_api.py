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
) -> dict[str, object]:
    try:
        parsed = json.loads(terms_json)
        extra_terms = [str(value) for value in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        extra_terms = []

    # Greek-first prompt: operational commands are spoken primarily in Greek,
    # with English refinery acronyms/tag names mixed into the sentence. Keeping
    # the instruction itself Greek avoids biasing short clips toward English.
    prompt_terms = list(dict.fromkeys([scope, *extra_terms]))[:80]
    prompt = (
        "Η ομιλία είναι στα Ελληνικά. Μετέγραψε στα Ελληνικά και κράτησε μόνο τους "
        "τεχνικούς όρους, ακρωνύμια και tags στην καθιερωμένη αγγλική γραφή τους. "
        "Πρόκειται για εντολή λειτουργίας διυλιστηρίου. Όροι αναφοράς: "
        + ", ".join(prompt_terms)
    )

    try:
        data = await audio.read()
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio clip is too large")
        raw = transcribe_wav(data, prompt=prompt)
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
        "local_only": True,
        "audio_retained": False,
    }
