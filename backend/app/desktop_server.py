from fastapi.middleware.cors import CORSMiddleware

from .bridge_api import router as bridge_router
from .dashboard_api import router as dashboard_router
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
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)
