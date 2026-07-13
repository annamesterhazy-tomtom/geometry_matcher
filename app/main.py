"""Entry point for GeometryMatcher: creates the pywebview window (loading
the built Angular UI) and a system tray icon to show/hide/quit it.

Run with (after `ng build` in frontend/):
    .venv\\Scripts\\python.exe -m app.main
"""
from __future__ import annotations

import sys
from pathlib import Path

import webview

from app.api import GeometryMatcherApi
from app.tray import create_tray_icon, run_tray_in_background

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_INDEX = REPO_ROOT / "frontend" / "dist" / "frontend" / "browser" / "index.html"


def _require_frontend_build() -> Path:
    if not FRONTEND_INDEX.exists():
        print(
            f"Angular build not found at {FRONTEND_INDEX}.\n"
            "Run `npm run build` (or `npx ng build`) inside frontend/ first.",
            file=sys.stderr,
        )
        sys.exit(1)
    return FRONTEND_INDEX


def main() -> None:
    index_path = _require_frontend_build()

    # Pass the plain filesystem path (not a file:// URI) so pywebview serves
    # it through its internal local HTTP server. With a raw file:// URI,
    # Angular's `<base href="/">`-relative asset requests resolve against
    # the filesystem root and fail to load (blank page).
    window = webview.create_window(
        "GeometryMatcher",
        url=str(index_path),
        js_api=GeometryMatcherApi(),
        width=900,
        height=700,
        hidden=True,  # start hidden; tray "Open" reveals it
    )

    def on_open() -> None:
        window.show()

    def on_quit() -> None:
        icon.stop()
        window.destroy()

    icon = create_tray_icon(on_open=on_open, on_quit=on_quit)
    run_tray_in_background(icon)

    # Show the window immediately on first launch too, not just via tray.
    webview.start(func=lambda: window.show())


if __name__ == "__main__":
    main()
