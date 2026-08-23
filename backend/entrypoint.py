from __future__ import annotations

import uvicorn

from app.desktop_server import app

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8765


def main() -> None:
    uvicorn.run(
        app,
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
