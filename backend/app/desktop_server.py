from fastapi.middleware.cors import CORSMiddleware

from .main import app

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
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
