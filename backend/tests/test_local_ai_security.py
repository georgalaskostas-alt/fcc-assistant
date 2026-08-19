from app.local_ai import _is_local_url


def test_local_ai_allows_loopback_only() -> None:
    assert _is_local_url("http://127.0.0.1:11434")
    assert _is_local_url("http://localhost:11434")
    assert _is_local_url("http://[::1]:11434")


def test_local_ai_rejects_external_hosts() -> None:
    assert not _is_local_url("https://api.openai.com")
    assert not _is_local_url("https://example.com:11434")
    assert not _is_local_url("http://192.168.1.10:11434")
