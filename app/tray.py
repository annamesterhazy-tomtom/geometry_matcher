"""System tray icon for GeometryMatcher.

Provides a small pystray icon with an Open/Quit menu. The tray icon itself
runs in its own thread (`start()` is non-blocking); the pywebview window
lifecycle is controlled via the callbacks passed in from `main.py`.
"""
from __future__ import annotations

import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw


def _build_icon_image(size: int = 64) -> Image.Image:
    """Draw a simple flat icon (a stylised "G" mark) so the app doesn't
    depend on an external image asset.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(26, 115, 232, 255),  # matches the UI's accent blue
    )
    draw.rectangle(
        [size * 0.5, size * 0.42, size - margin - 2, size * 0.58],
        fill=(26, 115, 232, 255),
    )
    draw.rectangle(
        [size * 0.42, size * 0.42, size * 0.58, size - margin - 2],
        fill=(255, 255, 255, 255),
    )
    return img


def create_tray_icon(on_open: Callable[[], None], on_quit: Callable[[], None]) -> pystray.Icon:
    """Build (but don't start) the tray icon with an Open/Quit menu."""
    menu = pystray.Menu(
        pystray.MenuItem("Open GeometryMatcher", lambda: on_open(), default=True),
        pystray.MenuItem("Quit", lambda: on_quit()),
    )
    return pystray.Icon("geometry_matcher", _build_icon_image(), "GeometryMatcher", menu)


def run_tray_in_background(icon: pystray.Icon) -> threading.Thread:
    """Run the tray icon's event loop in a daemon thread so it doesn't block
    the pywebview main-thread event loop.
    """
    thread = threading.Thread(target=icon.run, daemon=True)
    thread.start()
    return thread
