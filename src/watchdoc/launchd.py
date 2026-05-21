from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()

LABEL = "com.watchdoc.ocr"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = Path.home() / "Library" / "Logs" / "watchdoc.log"

BREW_DEPS = ["tesseract", "ghostscript", "terminal-notifier"]


def check_deps() -> None:
    """Check that required system dependencies are available."""
    missing = [dep for dep in BREW_DEPS if not shutil.which(dep)]
    if not missing:
        console.print("[green]\u2713[/green] system deps OK")
        return

    console.print(f"[yellow]![/yellow] missing: [bold]{', '.join(missing)}[/bold]")
    console.print(f"  run: [cyan]brew install {' '.join(missing)}[/cyan]\n")


def install(folder: Path) -> None:
    binary = shutil.which("watchdoc")
    if not binary:
        console.print("[red]could not find watchdoc binary on PATH[/red]")
        sys.exit(1)

    folder = folder.resolve()

    path = os.environ.get("PATH", "/usr/bin:/bin")
    if "/opt/homebrew/bin" not in path:
        path = f"/opt/homebrew/bin:{path}"

    plist: dict = {
        "Label": LABEL,
        "ProgramArguments": [binary, "watch", str(folder)],
        "KeepAlive": True,
        "EnvironmentVariables": {"PATH": path},
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
    }

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    if PLIST_PATH.exists():
        subprocess.run(
            ["launchctl", "unload", str(PLIST_PATH)],
            capture_output=True,
        )

    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)
    console.print(f"\n[green]\u2713[/green] [bold]launchd agent installed[/bold]")
    console.print(f"  watching  [cyan]{folder}[/cyan]")
    console.print(f"  plist     [dim]{PLIST_PATH}[/dim]")
    console.print(f"  logs      [dim]{LOG_PATH}[/dim]\n")


def uninstall() -> None:
    if not PLIST_PATH.exists():
        console.print("[dim]no agent installed[/dim]")
        return

    subprocess.run(
        ["launchctl", "unload", str(PLIST_PATH)],
        capture_output=True,
    )
    PLIST_PATH.unlink()
    console.print("[green]\u2713[/green] [bold]launchd agent removed[/bold]")
