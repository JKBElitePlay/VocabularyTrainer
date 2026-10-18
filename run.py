"""Local and packaged application entry point."""

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

if getattr(sys, "frozen", False):
    data_directory = (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        / "Vokabel-Freunde"
    )
    database_path = data_directory / "vokabeltrainer.db"
    os.environ.setdefault(
        "VOCABULARY_DATABASE_URL",
        f"sqlite:///{database_path.as_posix()}",
    )

from app.main import app


def select_port(host: str, requested_port: int) -> int:
    """Use the requested port, or ask Windows for a free one if it is busy."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, requested_port))
            return requested_port
        except OSError:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as fallback:
                fallback.bind((host, 0))
                port = fallback.getsockname()[1]
            print(f"Port {requested_port} ist belegt; verwende stattdessen Port {port}.")
            return port


def main() -> None:
    """Run the local web server and open the app in the default browser."""
    host = "127.0.0.1"
    port = select_port(host, int(os.environ.get("VOKABELTRAINER_PORT", "8000")))
    if getattr(sys, "frozen", False):
        url = f"http://{host}:{port}"
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
