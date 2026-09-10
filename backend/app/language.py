from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class LanguageDecision:
    detected: str
    response_language: str
    greek_chars: int
    latin_chars: int


def _letters(text: str) -> tuple[int, int]:
    normalized = unicodedata.normalize("NFKC", text)
    greek = sum(1 for ch in normalized.casefold() if "α" <= ch <= "ω")
    latin = sum(1 for ch in normalized.casefold() if "a" <= ch <= "z")
    return greek, latin


def detect_user_language(text: str) -> LanguageDecision:
    """Detect the interaction language without treating refinery jargon as English.

    Policy:
    - Any meaningful Greek sentence remains a Greek interaction even when it
      contains English refinery terms (feed flow, riser, FCC, HCU, etc.).
    - Pure English input gets English UI/answer behavior.
    - Mixed is exposed diagnostically, while response_language remains Greek
      when Greek is present so code-switching does not unexpectedly flip the UI.
    """
    greek, latin = _letters(text)
    if greek:
        detected = "mixed" if latin >= 3 else "el"
        return LanguageDecision(detected, "el", greek, latin)
    if latin:
        return LanguageDecision("en", "en", greek, latin)
    return LanguageDecision("unknown", "el", greek, latin)


def looks_like_spoken_command(text: str) -> bool:
    clean = re.sub(r"[^\w\s'-]+", " ", text, flags=re.UNICODE)
    words = [w for w in clean.split() if w]
    if len(words) >= 2:
        return True
    if not words:
        return False
    token = words[0].casefold()
    return token in {
        "add", "remove", "delete", "show", "hide", "restore", "change", "update",
        "βάλε", "βαλε", "βγάλε", "βγαλε", "δείξε", "δειξε", "άλλαξε", "αλλαξε",
    }
