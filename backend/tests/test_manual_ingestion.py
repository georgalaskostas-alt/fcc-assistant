from pathlib import Path

from app.manual_ingestion import ManualIngestionError, ingest_manual, search_manual_index


def test_text_manual_is_stored_and_searchable_locally(tmp_path: Path) -> None:
    manual_text = """
FCC REGENERATOR OPERATING NOTES

Normal operation requires monitoring regenerator temperature and oxygen.
The slide valve response should be evaluated together with reactor pressure balance.

REVAMP NOTE
After the revamp, the current operating practice limits FV-123 to 60 percent opening.
""".encode("utf-8")

    result = ingest_manual("FCC", "fcc-manual.txt", manual_text, root=tmp_path)

    assert Path(result.stored_path).exists()
    assert Path(result.index_path).exists()
    assert result.chunk_count >= 1
    assert result.character_count > 50

    matches = search_manual_index("fcc", "FV-123 revamp 60 percent", root=tmp_path)

    assert matches
    assert "FV-123" in matches[0]["text"]
    assert matches[0]["manual_name"] == "fcc-manual.txt"


def test_manual_search_is_scoped_to_process_unit(tmp_path: Path) -> None:
    ingest_manual("fcc", "fcc.txt", b"FCC catalyst circulation regenerator oxygen", root=tmp_path)
    ingest_manual("hcu", "hcu.txt", b"Hydrocracker hydrogen recycle compressor", root=tmp_path)

    assert search_manual_index("fcc", "hydrogen compressor", root=tmp_path) == []
    assert search_manual_index("hcu", "hydrogen compressor", root=tmp_path)


def test_unsupported_manual_type_is_rejected(tmp_path: Path) -> None:
    try:
        ingest_manual("fcc", "manual.exe", b"not a manual", root=tmp_path)
    except ManualIngestionError as exc:
        assert "Supported manual formats" in str(exc)
    else:
        raise AssertionError("Expected unsupported manual format to be rejected")
