from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from .site_model import load_site_model

router = APIRouter(prefix="/bridge/v1", tags=["bridge"])


def _site_or_http_error():
    try:
        return load_site_model()
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Invalid local site configuration: {exc}") from exc


@router.get("/capabilities")
def bridge_capabilities() -> dict[str, object]:
    site = _site_or_http_error()
    return {
        "contract_version": "1.0-draft",
        "service": "fcc-assistant-backend",
        "mode": "local",
        "read_only": True,
        "external_ai": False,
        "plant_write_access": False,
        "transport": {
            "scope": "loopback",
            "base_url": "http://127.0.0.1:8000",
        },
        "capabilities": [
            "health",
            "site_catalog",
            "dashboard_workspaces",
            "dashboard_commands",
            "simulator",
            "analytics",
            "reports",
            "local_ai",
        ],
        "site": {
            "name": site.name,
            "unit_count": len(site.units),
            "units": [unit.key for unit in site.units],
        },
    }


@router.get("/site")
def bridge_site_catalog() -> dict[str, object]:
    site = _site_or_http_error()
    return {
        "contract_version": "1.0-draft",
        "site": site.name,
        "read_only": True,
        "units": [asdict(unit) for unit in site.units],
    }
