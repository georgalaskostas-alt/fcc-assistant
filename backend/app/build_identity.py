"""Runtime identity for diagnosing which packaged backend is actually running."""
from __future__ import annotations

from typing import Any


def runtime_build_identity() -> dict[str, Any]:
    """Return embedded build metadata when packaged, with a safe dev fallback."""
    try:
        from ._build_info import BUILD_BRANCH, BUILD_SHA, BUILD_TIME_UTC  # type: ignore
    except ImportError:
        return {
            "git_sha": "development-unpackaged",
            "branch": "development",
            "built_at_utc": None,
            "embedded": False,
        }
    return {
        "git_sha": BUILD_SHA,
        "branch": BUILD_BRANCH,
        "built_at_utc": BUILD_TIME_UTC,
        "embedded": True,
    }
