"""Show the approval window. Stdlib only, Python 3.9 compatible.

The window itself is awin/window.js, run by /usr/bin/osascript. This module
writes the page to a private temp file, runs the script and reads one word.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from awin.render import LEVEL_COLOR, render_html, window_height
from awin.request import Request

OSASCRIPT = "/usr/bin/osascript"
WINDOW_JS = Path(__file__).with_name("window.js")
MAX_TIMEOUT = 100  # docs/mediciones.md: Cursor cuts a tool at 120 s, minus 20 s of margin
DEFAULT_TIMEOUT = MAX_TIMEOUT


class Unavailable(Exception):
    """No window could be shown (not macOS, no osascript, or osascript failed)."""


def available(platform: Optional[str] = None, osascript: str = OSASCRIPT) -> bool:
    return (platform or sys.platform) == "darwin" and os.access(osascript, os.X_OK)


def _run(argv, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, **kwargs)


def ask(req: Request, timeout: int, runner: Optional[Callable] = None) -> bool:
    """True only when a person clicked Approve. Timeout, close and Cancelar are False."""
    if not available():
        raise Unavailable("no approval window here (needs macOS and /usr/bin/osascript)")
    run = runner or _run
    tint = LEVEL_COLOR[req.reversibility] if req.style == "tag" else ""
    fd, path = tempfile.mkstemp(prefix="awin-", suffix=".html")  # created 0600
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(render_html(req))
        argv = [OSASCRIPT, "-l", "JavaScript", str(WINDOW_JS), path,
                f"{req.skill} · Aprobación", req.approve_label, str(window_height(req)), tint]
        try:
            done = run(argv, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False  # the window was up and nobody clicked
        except OSError as exc:
            raise Unavailable(f"the approval window could not start ({exc})") from None
        if done.returncode != 0:
            raise Unavailable(f"the approval window failed (osascript exit {done.returncode})")
        return (done.stdout or "").strip() == "approved"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
