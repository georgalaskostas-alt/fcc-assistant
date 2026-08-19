from app.settings import Settings


def test_standalone_ai_defaults_to_embedded_llama_cpp() -> None:
    settings = Settings(_env_file=None)
    assert settings.prefer_travis_ai is False
    assert settings.local_ai_runtime == "llama_cpp"
    assert settings.local_ai_url == "http://127.0.0.1:8081"
    assert settings.travis_ai_url == "http://127.0.0.1:8765"


def test_embedded_ai_model_is_local_gguf_path() -> None:
    settings = Settings(_env_file=None)
    assert settings.local_ai_model_path.endswith(".gguf")
    assert settings.local_ai_binary_path.endswith("llama-server")
