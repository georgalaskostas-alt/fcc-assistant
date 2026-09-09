from app.speech_domain import normalize_transcript


def test_natural_greek_keeps_ordinary_words_and_normalizes_hydrocracker():
    decision = normalize_transcript(
        "Θέλω να μου βάλεις ένα γράφημα reaction temperature στη μονάδα χαιντρο κράκερ"
    )
    assert "Hydrocracker" in decision.normalized_text
    assert "reactor temperature" in decision.normalized_text
    assert "Θέλω" in decision.normalized_text
    assert decision.level != "low"


def test_hcu_spoken_letters_are_normalized_without_rewriting_sentence():
    decision = normalize_transcript("Βάλε το γράφημα στο έιτς σι γιου")
    assert "HCU" in decision.normalized_text
    assert "γράφημα" in decision.normalized_text


def test_fcc_asr_confusion_is_repaired():
    decision = normalize_transcript("Βάλε reaction temperature στο SCC")
    assert "FCC" in decision.normalized_text
    assert "reactor temperature" in decision.normalized_text


def test_latin_noise_without_refinery_evidence_is_rejected():
    decision = normalize_transcript("The Lona Valo")
    assert decision.normalized_text == ""
    assert decision.level == "low"
    assert decision.execute_immediately is False


def test_general_greek_words_are_not_fuzzy_rewritten_into_tags():
    phrase = "Μπορείς να μου δείξεις τι έγινε στη μονάδα από το πρωί μέχρι τώρα"
    decision = normalize_transcript(phrase)
    assert decision.normalized_text == phrase
