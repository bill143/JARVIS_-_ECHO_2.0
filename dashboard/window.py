"""Open the dashboard as its own app window (Edge --app), else the default browser."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

WINDOW_SIZE = "1500,940"


def find_edge() -> str | None:
    found = shutil.which("msedge")
    if found:
        return found
    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles"), os.getenv("LOCALAPPDATA")):
        if base:
            candidate = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if candidate.exists():
                return str(candidate)
    return None


def open_app_window(url: str) -> str:
    """Launch the window; return how it was opened ("edge-app" or "browser")."""
    edge = find_edge()
    if edge:
        # A dedicated profile keeps the JARVIS window separate from Bill's normal
        # Edge session (own taskbar entry, no tab strip, remembers its size).
        profile = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "JARVIS" / "edge-app"
        profile.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(  # noqa: S603 - fixed executable, no shell
                [edge, f"--app={url}", f"--window-size={WINDOW_SIZE}", f"--user-data-dir={profile}",
                 "--no-first-run", "--no-default-browser-check"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return "edge-app"
        except OSError as exc:
            logger.warning("Edge app window failed (%s); using the default browser.", exc)
    webbrowser.open(url)
    return "browser"
