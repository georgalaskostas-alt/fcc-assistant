from pathlib import Path

from app.model_manager import LocalModelManager


def test_model_manager_uses_user_local_path() -> None:
    manager = LocalModelManager()
    assert manager.model.path == Path("~/.fcc-assistant/models/Qwen3-4B-Q4_K_M.gguf").expanduser()


def test_model_manager_points_to_official_qwen_gguf() -> None:
    manager = LocalModelManager()
    assert manager.model.url.startswith("https://huggingface.co/Qwen/Qwen3-4B-GGUF/")
    assert manager.model.name == "Qwen3-4B-Q4_K_M"
    assert len(manager.model.sha256) == 64


def test_status_declares_no_process_data_upload() -> None:
    manager = LocalModelManager()
    assert manager.status()["process_data_uploaded"] is False
