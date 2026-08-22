from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from .site_model import default_site_model

router = APIRouter(prefix="/bridge/v1", tags=["bridge"])


@router.get("/capabilities")
def bridge_capabilities() -> dict[str, object]:
    site = default_site_model()
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
    site = default_site_model()
    return {
        "contract_version": "1.0-draft",
        "site": site.name,
        "read_only": True,
        "units": [asdict(unit) for unit in site.units],
    }
