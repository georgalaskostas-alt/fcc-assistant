from fastapi import FastAPI

app = FastAPI(
    title="FCC Assistant Local API",
    version="0.1.0",
    description="Local backend for FCC process analysis and reporting.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "fcc-assistant-backend",
        "mode": "local",
    }


@app.get("/api/v1/system/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "pi_web_api": "not_configured",
        "local_ai": "not_configured",
        "plant_write_access": False,
        "features": [
            "pi-read-only",
            "engineering-analytics",
            "shift-reports",
            "local-ai-assistant",
        ],
    }
