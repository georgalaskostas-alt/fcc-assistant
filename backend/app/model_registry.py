from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class ModelProfile:
    tier: str
    min_ram_gb: float
    max_ram_gb: float | None
    target_parameters: str
    quantization: str
    context_size: int
    description: str


MODEL_PROFILES = [
    ModelProfile(
        tier="light",
        min_ram_gb=0,
        max_ram_gb=12,
        target_parameters="3B-4B",
        quantization="Q4_K_M",
        context_size=4096,
        description="For 8 GB class laptops; prioritizes responsiveness and memory safety.",
    ),
    ModelProfile(
        tier="medium",
        min_ram_gb=12,
        max_ram_gb=28,
        target_parameters="7B-14B",
        quantization="Q4_K_M",
        context_size=8192,
        description="Balanced local reasoning for 16-24 GB systems.",
    ),
    ModelProfile(
        tier="high",
        min_ram_gb=28,
        max_ram_gb=56,
        target_parameters="14B-32B",
        quantization="Q4_K_M/Q5_K_M",
        context_size=16384,
        description="Strong local reasoning for 32-48 GB systems or high-memory GPUs.",
    ),
    ModelProfile(
        tier="ultra",
        min_ram_gb=56,
        max_ram_gb=None,
        target_parameters="30B-70B",
        quantization="Q4_K_M/Q5_K_M",
        context_size=32768,
        description="Maximum local reasoning tier for 64 GB+ systems or workstation GPUs.",
    ),
]


def select_profile(ram_gb: float, gpu_name: str = "") -> ModelProfile:
    gpu = gpu_name.lower()

    # Dedicated 24 GB+ GPUs can support a higher tier than host RAM alone suggests.
    if any(token in gpu for token in ("5090", "4090", "3090", "a6000", "48gb")):
        if ram_gb >= 48 or "48gb" in gpu or "a6000" in gpu:
            return next(profile for profile in MODEL_PROFILES if profile.tier == "ultra")
        return next(profile for profile in MODEL_PROFILES if profile.tier == "high")

    for profile in MODEL_PROFILES:
        if ram_gb >= profile.min_ram_gb and (profile.max_ram_gb is None or ram_gb < profile.max_ram_gb):
            return profile
    return MODEL_PROFILES[0]


def registry_payload() -> list[dict[str, Any]]:
    return [asdict(profile) for profile in MODEL_PROFILES]
