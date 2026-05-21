from __future__ import annotations

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


def _ensure_brew_deps() -> None:
    brew = shutil.which("brew")
    if not brew:
        console.print("[red]Homebrew not found[/red] \u2014 install it from https://brew.sh")
        sys.exit(1)

    installed = subprocess.run(
        [brew, "list", "--formula", "-1"],
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    missing = [dep for dep in BREW_DEPS if dep not in installed]
    if not missing:
        console.print("[green]\u2713[/green] brew deps already installed")
        return

    console.print(f"[bold]Installing[/bold] {', '.join(missing)}\u2026")
    subprocess.run([brew, "install", *missing], check=True)
    console.print("[green]\u2713[/green] brew deps installed")


def install(folder: Path) -> None:
    _ensure_brew_deps()

    binary = shutil.which("watchdoc")
    if not binary:
        console.print("[red]could not find watchdoc binary on PATH[/red]")
        sys.exit(1)

    folder = folder.resolve()

    plist: dict = {
        "Label": LABEL,
        "ProgramArguments": [binary, "run", str(folder)],
        "WatchPaths": [str(folder)],
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
