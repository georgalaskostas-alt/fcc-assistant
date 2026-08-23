from app.speech_domain import normalize_transcript


def test_normalizes_greek_hydrocracker_pronunciation():
    result = normalize_transcript("βάλε τροφοδοσία στο χαιντρο κρακερ για οκτώ ώρες")
    assert "Hydrocracker" in result.normalized_text
    assert result.confidence > 0.6


def test_normalizes_common_fcc_process_terms():
    result = normalize_transcript("δείξε θερμοκρασία αντίδρασης στο εφ σι σι και οξυγόνο regenerator")
    assert "FCC" in result.normalized_text
    assert "reactor temperature" in result.normalized_text


def test_custom_site_term_is_preserved_and_can_raise_domain_context():
    result = normalize_transcript("δείξε το FV-123", extra_terms=["FV-123"])
    assert "FV-123" in result.normalized_text


def test_empty_transcript_is_low_confidence_and_never_executes():
    result = normalize_transcript("   ")
    assert result.level == "low"
    assert result.execute_immediately is False


def test_medium_or_low_confidence_does_not_execute_blindly():
    result = normalize_transcript("γράφημα")
    assert result.execute_immediately is False


def test_rejects_latin_only_whisper_hallucination_without_domain_context():
    result = normalize_transcript("The Lona Valo")
    assert result.raw_text == "The Lona Valo"
    assert result.normalized_text == ""
    assert result.level == "low"
    assert result.execute_immediately is False


def test_allows_mixed_or_technical_english_when_it_has_refinery_context():
    result = normalize_transcript("FCC feed flow")
    assert "FCC" in result.normalized_text
    assert "feed flow" in result.normalized_text
    assert result.normalized_text != ""


def test_corrects_scc_to_fcc():
    result = normalize_transcript("βάλε γράφημα feed flow του SCC")
    assert "FCC" in result.normalized_text
