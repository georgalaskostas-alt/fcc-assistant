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


# Layer 1/2 vocabulary: only high-value, stable refinery entities and command
# words belong here. Ordinary Greek words must never be fuzzy-matched against a
# huge tag list because that can corrupt an otherwise correct Whisper result.
_CRITICAL_TERMS: dict[str, tuple[str, ...]] = {
    "FCC": (
        "fcc", "f c c", "scc", "s c c", "εφ σι σι", "εφσισι", "φσισι", "ες σι σι",
    ),
    "Hydrocracker": (
        "hydrocracker", "hydro cracker", "hydrocraker", "hydro craker",
        "χαιντροκρακερ", "χαιντρο κρακερ", "χαινδροκρακερ", "χαινδρο κρακερ",
        "υδροκρακερ", "υδρο κρακερ", "χάιντροκρακερ", "χάιντρο κράκερ",
    ),
    "HCU": (
        "hcu", "h c u", "ητς σι γιου", "εϊτς σι γιου", "έιτς σι γιου",
    ),
    "VDU": ("vdu", "v d u", "βι ντι γιου", "βιντιγιου"),
    "LCO": ("lco", "l c o", "ελ σι ο", "ελσιο"),
    "slurry": ("slurry", "σλαρι", "σλάρι"),
    "regenerator": ("regenerator", "ριτζενερεϊτορ", "ριτζενερετορ", "αναγεννητης", "αναγεννητή"),
    "riser": ("riser", "ραιζερ", "ράιζερ"),
    "stripper": ("stripper", "στριπερ", "στρίπερ"),
    "main fractionator": (
        "main fractionator", "μειν φρακσιονειτορ", "κεντρικος κλασματωτης", "κεντρικός κλασματωτής",
    ),
    "feed flow": (
        "feed flow", "feed_flow", "φιντ φλοου", "τροφοδοσια", "τροφοδοσία",
        "παροχη τροφοδοσιας", "παροχή τροφοδοσίας",
    ),
    "reactor temperature": (
        "reactor temperature", "reaction temperature", "reactor_temperature", "reaction_temperature",
        "θερμοκρασια αντιδραστηρα", "θερμοκρασία αντιδραστήρα",
        "θερμοκρασια αντιδρασης", "θερμοκρασία αντίδρασης",
    ),
    "αφαίρεσε": (
        "αφαίρεσε", "αφαιρεσε", "αφαιρέσει", "αφαιρεσει", "αφαιρεί", "αφαιρει",
        "αφέρει", "αφερει", "βγάλε", "βγαλε",
    ),
    "γράφημα": ("γράφημα", "γραφημα", "διάγραμμα", "διαγραμμα", "chart", "trend"),
}

# Only these canonical concepts are allowed to use fuzzy correction. This is
# intentionally much smaller than the complete refinery/tag vocabulary.
_FUZZY_CANONICALS = {
    "FCC", "Hydrocracker", "HCU", "VDU", "LCO",
    "slurry", "regenerator", "riser", "stripper",
    "feed flow", "reactor temperature", "αφαίρεσε", "γράφημα",
}

_HALLUCINATED_PREFIXES = (
    "πρόεδρε", "προεδρε", "λοιπόν", "λοιπον",
)


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9α-ω\s._/-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _clean_raw(value: str) -> str:
    value = value.replace("’", "'").replace("“", '"').replace("”", '"')
    value = re.sub(r"\s+", " ", value).strip()
    folded = _fold(value)
    for prefix in _HALLUCINATED_PREFIXES:
        fp = _fold(prefix)
        if folded == fp or folded.startswith(fp + " "):
            value = re.sub(rf"^\s*{re.escape(prefix)}\s*[:;,.-]?\s*", "", value, flags=re.IGNORECASE)
            break
    return value.strip()


def _contains_greek(value: str) -> bool:
    return any("α" <= ch <= "ω" for ch in _fold(value))


def build_lexicon(extra_terms: Iterable[str] = ()) -> dict[str, tuple[str, ...]]:
    """Build the exact-match lexicon.

    Extra site terms are exact-match only. They are deliberately not added to
    the fuzzy pool, preventing arbitrary Greek words from being transformed into
    tags merely because they have similar spelling.
    """
    lexicon = dict(_CRITICAL_TERMS)
    for term in extra_terms:
        clean = term.strip()
        if not clean:
            continue
        current = list(lexicon.get(clean, ()))
        current.extend((clean, clean.replace("-", " "), clean.replace("_", " ")))
        lexicon[clean] = tuple(dict.fromkeys(current))
    return lexicon


def _domain_evidence_count(value: str, lexicon: dict[str, tuple[str, ...]]) -> int:
    folded = _fold(value)
    matched: set[str] = set()
    for canonical, variants in lexicon.items():
        for candidate in (canonical, *variants):
            token = _fold(candidate)
            if len(token) >= 3 and token in folded:
                matched.add(canonical)
                break
    return len(matched)


def _phrase_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _fold(a), _fold(b)).ratio()


def _replace_folded_phrase(text: str, source: str, target: str) -> tuple[str, bool]:
    """Replace a phrase using accent/case-insensitive token comparison.

    Regex replacement against the raw source is insufficient when Whisper emits
    the same Greek word with different accents. Matching token windows on folded
    text keeps the correction deterministic.
    """
    source_tokens = _fold(source).split()
    if not source_tokens:
        return text, False
    words = text.split()
    width = len(source_tokens)
    for index in range(0, len(words) - width + 1):
        chunk = " ".join(words[index:index + width])
        if _fold(chunk) == " ".join(source_tokens):
            return " ".join(words[:index] + [target] + words[index + width:]), True
    return text, False


def _exact_phrase_layer(text: str, lexicon: dict[str, tuple[str, ...]]) -> tuple[str, list[DomainCorrection]]:
    normalized = text
    corrections: list[DomainCorrection] = []
    candidates: list[tuple[str, str]] = []
    for canonical, variants in lexicon.items():
        for variant in (canonical, *variants):
            candidates.append((variant, canonical))
    candidates.sort(key=lambda item: len(_fold(item[0])), reverse=True)

    for variant, canonical in candidates:
        fv = _fold(variant)
        if len(fv) < 3 or fv not in _fold(normalized):
            continue
        updated, changed = _replace_folded_phrase(normalized, variant, canonical)
        if changed and updated != normalized:
            corrections.append(DomainCorrection(variant, canonical, 1.0))
            normalized = updated
    return normalized, corrections


def _fuzzy_critical_layer(text: str) -> tuple[str, list[DomainCorrection]]:
    """Conservatively repair ASR damage only around critical refinery entities.

    We consider 1-3 word windows and demand a high similarity score. General
    site tags and normal Greek vocabulary are excluded from fuzzy matching.
    """
    words = text.split()
    corrections: list[DomainCorrection] = []
    index = 0
    while index < len(words):
        best: tuple[float, int, str] | None = None
        for width in (3, 2, 1):
            if index + width > len(words):
                continue
            chunk = " ".join(words[index:index + width])
            folded_chunk = _fold(chunk)
            if len(folded_chunk) < 3 or folded_chunk.isdigit():
                continue
            for canonical in _FUZZY_CANONICALS:
                variants = _CRITICAL_TERMS.get(canonical, ())
                for candidate in (canonical, *variants):
                    fc = _fold(candidate)
                    # Do not compare radically different token lengths.
                    if abs(len(fc) - len(folded_chunk)) > max(2, int(len(fc) * 0.25)):
                        continue
                    score = _phrase_score(folded_chunk, fc)
                    threshold = 0.91 if width == 1 else 0.88
                    if score >= threshold and _fold(canonical) != folded_chunk:
                        if best is None or score > best[0]:
                            best = (score, width, canonical)
        if best is None:
            index += 1
            continue
        score, width, canonical = best
        source = " ".join(words[index:index + width])
        words[index:index + width] = [canonical]
        corrections.append(DomainCorrection(source, canonical, round(score, 3)))
        index += 1
    return " ".join(words), corrections


def normalize_transcript(text: str, extra_terms: Iterable[str] = ()) -> SpeechDecision:
    raw = _clean_raw(text)
    if not raw:
        return SpeechDecision(raw, "", 0.0, "low", False, ())

    lexicon = build_lexicon(extra_terms)
    pre_hits = _domain_evidence_count(raw, lexicon)

    # Reject likely English hallucinations from silence/noise. Legitimate mixed
    # Greek/English refinery speech passes because it contains Greek or real
    # domain evidence.
    if not _contains_greek(raw) and pre_hits == 0:
        return SpeechDecision(raw, "", 0.05, "low", False, ())

    # Layer 1: deterministic exact/phonetic aliases.
    normalized, exact_corrections = _exact_phrase_layer(raw, lexicon)

    # Layer 2: very conservative fuzzy repair of only critical refinery entities.
    normalized, fuzzy_corrections = _fuzzy_critical_layer(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    corrections = [*exact_corrections, *fuzzy_corrections]

    post_hits = _domain_evidence_count(normalized, lexicon)
    word_count = len(normalized.split())
    greek_score = 1.0 if _contains_greek(normalized) else 0.62
    length_score = min(1.0, max(0.38, word_count / 7.0))
    evidence_score = min(1.0, 0.50 + 0.13 * max(pre_hits, post_hits, len(corrections)))

    # Large fuzzy rewrites are a warning sign, not a reason to become more
    # confident. Exact known aliases are safe; fuzzy repairs get a small penalty.
    fuzzy_penalty = min(0.18, 0.045 * len(fuzzy_corrections))
    confidence = 0.38 * length_score + 0.34 * evidence_score + 0.28 * greek_score - fuzzy_penalty
    confidence = max(0.0, min(0.99, confidence))

    if confidence >= 0.84:
        level = "high"
        execute = True
    elif confidence >= 0.66:
        level = "medium"
        execute = False
    else:
        level = "low"
        execute = False

    return SpeechDecision(
        raw_text=raw,
        normalized_text=normalized,
        confidence=round(confidence, 3),
        level=level,
        execute_immediately=execute,
        corrections=tuple(corrections),
    )
