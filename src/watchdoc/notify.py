from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_ICON = Path(__file__).with_name("icon.png")


def notify(title: str, message: str) -> None:
    """Send a macOS notification banner.

    Prefers terminal-notifier (custom icon support) over osascript.
    Silently no-ops on failure.
    """
    try:
        tn = shutil.which("terminal-notifier")
        if tn and _ICON.exists():
            subprocess.run(
                [tn, "-title", title, "-message", message, "-appIcon", str(_ICON)],
                check=True,
                capture_output=True,
            )
            return

        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "{title}"',
            ],
            check=True,
            capture_output=True,
        )
    except Exception:
        log.debug("notification failed", exc_info=True)
