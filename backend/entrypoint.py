from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.desktop_server:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
