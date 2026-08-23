from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Iterable


@dataclass(frozen=True)
class DomainCorrection:
    source: str
    target: str
    score: float


@dataclass(frozen=True)
class SpeechDecision:
    raw_text: str
    normalized_text: str
    confidence: float
    level: str
    execute_immediately: bool
    corrections: tuple[DomainCorrection, ...]


_BUILTIN_TERMS: dict[str, tuple[str, ...]] = {
    "FCC": ("fcc", "f c c", "scc", "s c c", "εφ σι σι", "εφσισι", "φσισι", "ες σι σι"),
    "Hydrocracker": (
        "hydrocracker",
        "hydro cracker",
        "hydrocraker",
        "χαιντροκρακερ",
        "χαιντρο κρακερ",
        "χαινδροκρακερ",
        "υδροκρακερ",
        "υδρο κρακερ",
    ),
    "HCU": ("hcu", "h c u", "ητς σι γιου", "εϊτς σι γιου"),
    "VDU": ("vdu", "v d u", "βι ντι γιου", "βιντιγιου"),
    "LCO": ("lco", "l c o", "ελ σι ο", "ελσιo", "ελσιο"),
    "slurry": ("slurry", "σλαρι", "σλάρι"),
    "regenerator": ("regenerator", "ριτζενερεϊτορ", "ριτζενερετορ", "αναγεννητης", "αναγεννητή"),
    "riser": ("riser", "ραιζερ", "ράιζερ"),
    "stripper": ("stripper", "στριπερ", "στρίπερ"),
    "main fractionator": ("main fractionator", "μειν φρακσιονειτορ", "κεντρικος κλασματωτης", "κεντρικός κλασματωτής"),
    "feed flow": ("feed flow", "feed_flow", "φιντ φλοου", "τροφοδοσια", "τροφοδοσία", "παροχη τροφοδοσιας", "παροχή τροφοδοσίας"),
    "reactor temperature": ("reactor temperature", "reactor_temperature", "θερμοκρασια αντιδραστηρα", "θερμοκρασία αντιδραστήρα", "θερμοκρασια αντιδρασης", "θερμοκρασία αντίδρασης"),
}


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9α-ω\s._/-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def build_lexicon(extra_terms: Iterable[str] = ()) -> dict[str, tuple[str, ...]]:
    lexicon = dict(_BUILTIN_TERMS)
    for term in extra_terms:
        clean = term.strip()
        if not clean:
            continue
        current = list(lexicon.get(clean, ()))
        current.extend((clean, clean.replace("-", " "), clean.replace("_", " ")))
        lexicon[clean] = tuple(dict.fromkeys(current))
    return lexicon


def _phrase_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _fold(a), _fold(b)).ratio()


def normalize_transcript(text: str, extra_terms: Iterable[str] = ()) -> SpeechDecision:
    raw = text.strip()
    if not raw:
        return SpeechDecision(raw, "", 0.0, "low", False, ())

    normalized = raw
    folded_text = _fold(raw)
    corrections: list[DomainCorrection] = []
    lexicon = build_lexicon(extra_terms)

    candidates: list[tuple[str, str]] = []
    for canonical, variants in lexicon.items():
        for variant in variants:
            candidates.append((variant, canonical))
    candidates.sort(key=lambda item: len(_fold(item[0])), reverse=True)

    working_folded = folded_text
    for variant, canonical in candidates:
        folded_variant = _fold(variant)
        if len(folded_variant) < 3:
            continue
        if folded_variant in working_folded:
            pattern = re.compile(re.escape(variant), flags=re.IGNORECASE)
            before = normalized
            normalized = pattern.sub(canonical, normalized)
            if normalized == before:
                words = normalized.split()
                target_words = folded_variant.split()
                for i in range(0, len(words) - len(target_words) + 1):
                    chunk = " ".join(words[i : i + len(target_words)])
                    if _fold(chunk) == folded_variant:
                        normalized = " ".join(words[:i] + [canonical] + words[i + len(target_words) :])
                        break
            if normalized != before:
                corrections.append(DomainCorrection(variant, canonical, 1.0))
                working_folded = _fold(normalized)

    words = normalized.split()
    for i, word in enumerate(words):
        folded_word = _fold(word)
        if len(folded_word) < 3 or folded_word.isdigit():
            continue
        best: tuple[float, str, str] | None = None
        for canonical, variants in lexicon.items():
            folded_canonical = _fold(canonical)
            # Acronyms such as FCC are especially prone to one-letter STT errors.
            if len(folded_word) == 3 and len(folded_canonical) == 3:
                mismatches = sum(a != b for a, b in zip(folded_word, folded_canonical))
                if mismatches == 1:
                    score = 0.93
                    if best is None or score > best[0]:
                        best = (score, word, canonical)
            for variant in variants:
                fv = _fold(variant)
                if " " in fv or abs(len(fv) - len(folded_word)) > 3:
                    continue
                score = _phrase_score(folded_word, fv)
                if score >= 0.86 and (best is None or score > best[0]):
                    best = (score, variant, canonical)
        if best and _fold(best[2]) != folded_word:
            words[i] = best[2]
            corrections.append(DomainCorrection(word, best[2], round(best[0], 3)))
    normalized = " ".join(words)

    length_score = min(1.0, max(0.25, len(normalized.split()) / 7.0))
    domain_hits = len(corrections)
    domain_score = min(1.0, 0.55 + 0.12 * domain_hits)
    punctuation_penalty = 0.08 if raw.count("?") + raw.count("!") > 4 else 0.0
    confidence = max(0.0, min(0.99, 0.52 * length_score + 0.48 * domain_score - punctuation_penalty))

    if confidence >= 0.82:
        level = "high"
        execute = True
    elif confidence >= 0.62:
        level = "medium"
        execute = False
    else:
        level = "low"
        execute = False

    return SpeechDecision(
        raw_text=raw,
        normalized_text=normalized.strip(),
        confidence=round(confidence, 3),
        level=level,
        execute_immediately=execute,
        corrections=tuple(corrections),
    )
