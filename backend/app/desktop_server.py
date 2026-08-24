from fastapi.middleware.cors import CORSMiddleware

from .bridge_api import router as bridge_router
from .dashboard_api import router as dashboard_router
from .diagnostic_trace import append_trace
from .embedded_runtime import EmbeddedAIRuntime, EmbeddedRuntimeError
from .main import app
from .refinery_intelligence_api import router as refinery_intelligence_router
from .site_simulator_api import router as site_simulator_router
from .speech_api import router as speech_router
from .unit_knowledge_api import router as unit_knowledge_router

app.include_router(dashboard_router)
app.include_router(bridge_router)
app.include_router(site_simulator_router)
app.include_router(unit_knowledge_router)
app.include_router(refinery_intelligence_router)
app.include_router(speech_router)


@app.on_event("startup")
def start_embedded_ai_runtime() -> None:
    """Desktop backend owns the local model lifecycle; failures are traced but do not crash UI."""
    runtime = EmbeddedAIRuntime()
    try:
        state = runtime.start()
        append_trace("ai.runtime.start", {"running": state.running, "ready": state.ready, "pid": state.pid, "endpoint": state.endpoint, "detail": state.detail})
    except EmbeddedRuntimeError as exc:
        append_trace("ai.runtime.error", {"error": str(exc), "readiness": runtime.readiness()})


@app.on_event("shutdown")
def stop_embedded_ai_runtime() -> None:
    try:
        state = EmbeddedAIRuntime().stop()
        append_trace("ai.runtime.stop", {"running": state.running, "ready": state.ready})
    except EmbeddedRuntimeError as exc:
        append_trace("ai.runtime.stop_error", {"error": str(exc)})


# Desktop-only local origins. This does not expose the backend to the internet;
# it only allows the local Vite/Tauri webview to call the loopback API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
