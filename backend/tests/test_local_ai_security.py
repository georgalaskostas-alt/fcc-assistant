import pytest

from app.local_ai import LocalAIClient, LocalAIError, _is_loopback_host
from app.settings import get_settings


def test_loopback_detection() -> None:
    assert _is_loopback_host("localhost") is True
    assert _is_loopback_host("127.0.0.1") is True
    assert _is_loopback_host("::1") is True
    assert _is_loopback_host("8.8.8.8") is False
    assert _is_loopback_host("example.com") is False


def test_remote_ai_endpoint_is_blocked(monkeypatch) -> None:
    monkeypatch.setenv("FCC_LOCAL_AI_URL", "https://example.com")
    monkeypatch.setenv("FCC_LOCAL_AI_MODEL", "test-model")
    get_settings.cache_clear()
    with pytest.raises(LocalAIError, match="Remote AI endpoints are blocked"):
        LocalAIClient()
    get_settings.cache_clear()
