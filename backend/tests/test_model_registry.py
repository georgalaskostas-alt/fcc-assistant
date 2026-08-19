from app.model_registry import select_profile


def test_8gb_machine_uses_light_profile() -> None:
    profile = select_profile(8.0, "Apple M2")
    assert profile.tier == "light"
    assert profile.target_parameters == "3B-4B"


def test_16gb_machine_uses_medium_profile() -> None:
    assert select_profile(16.0, "Apple M2 Pro").tier == "medium"


def test_32gb_machine_uses_high_profile() -> None:
    assert select_profile(32.0, "Apple M3 Max").tier == "high"


def test_24gb_class_gpu_promotes_to_high_profile() -> None:
    assert select_profile(16.0, "NVIDIA GeForce RTX 4090").tier == "high"


def test_64gb_machine_uses_ultra_profile() -> None:
    assert select_profile(64.0, "Apple M4 Max").tier == "ultra"
