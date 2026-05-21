from __future__ import annotations

import argparse
import logging
import queue
import sys
import threading
import time
from pathlib import Path

import ocrmypdf
from rich.console import Console
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from watchdoc.launchd import install, uninstall
from watchdoc.notify import notify

console = Console()

SETTLE_INTERVAL = 2
SETTLE_ATTEMPTS = 10


def _wait_for_settle(path: Path) -> None:
    prev_size = -1
    for _ in range(SETTLE_ATTEMPTS):
        time.sleep(SETTLE_INTERVAL)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return
        if size == prev_size:
            return
        prev_size = size


def _process_pdf(path: Path, output_dir: Path | None) -> str:
    """OCR a single PDF. Returns 'ok', 'skip', or 'fail'."""
    if output_dir:
        target = output_dir / path.name
        tmp = None
    else:
        tmp = path.with_suffix(".pdf.tmp")
        target = tmp

    try:
        result = ocrmypdf.ocr(
            path,
            target,
            mode="redo",
            progress_bar=False,
        )
    except Exception as exc:
        console.print(f"  [red]x[/red] {path.name}  [dim]{exc}[/dim]")
        if tmp and tmp.exists():
            tmp.unlink()
        return "fail"

    if result == ocrmypdf.ExitCode.ok:
        if tmp:
            tmp.replace(path)
        console.print(f"  [green]\u2713[/green] {path.name}")
        return "ok"

    if result == ocrmypdf.ExitCode.already_done_ocr:
        if tmp and tmp.exists():
            tmp.unlink()
        console.print(f"  [yellow]\u2013[/yellow] {path.name}  [dim]already has OCR[/dim]")
        return "skip"

    if tmp and tmp.exists():
        tmp.unlink()
    console.print(f"  [red]x[/red] {path.name}  [dim]exit code {result}[/dim]")
    return "fail"


def process_folder(folder: Path, output_dir: Path | None = None) -> None:
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        console.print(f"[dim]no PDFs in {folder}[/dim]")
        return

    console.print(f"\n[bold]Processing {len(pdfs)} PDF(s)[/bold] in {folder}\n")
    notify("watchdoc", f"Processing {len(pdfs)} PDF(s)\u2026")

    counts: dict[str, int] = {"ok": 0, "skip": 0, "fail": 0}
    for pdf in pdfs:
        _wait_for_settle(pdf)
        if not pdf.exists():
            continue
        result = _process_pdf(pdf, output_dir)
        counts[result] += 1

    parts = []
    if counts["ok"]:
        parts.append(f"[green]{counts['ok']} processed[/green]")
    if counts["skip"]:
        parts.append(f"[yellow]{counts['skip']} skipped[/yellow]")
    if counts["fail"]:
        parts.append(f"[red]{counts['fail']} failed[/red]")
    console.print(f"\n[bold]Done[/bold] \u2014 {', '.join(parts)}\n")
    notify("watchdoc", f"Done \u2014 {counts['ok']} processed, {counts['skip']} skipped, {counts['fail']} failed")


class _PDFHandler(FileSystemEventHandler):
    """Enqueues new PDFs for processing on a worker thread."""

    def __init__(self, output_dir: Path | None) -> None:
        self._output_dir = output_dir
        self._q: queue.Queue[Path] = queue.Queue()
        self._worker = threading.Thread(target=self._drain, daemon=True)
        self._worker.start()

    def on_created(self, event):  # noqa: ANN001
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".pdf":
            self._q.put(path)

    def _drain(self) -> None:
        while True:
            path = self._q.get()
            console.print(f"\n[bold cyan]\u25cf[/bold cyan] [bold]{path.name}[/bold] detected")
            _wait_for_settle(path)
            if not path.exists():
                console.print("  [dim]file disappeared, skipping[/dim]")
                continue
            notify("watchdoc", f"Processing {path.name}\u2026")
            with console.status("  OCR in progress\u2026", spinner="dots"):
                result = _process_pdf(path, self._output_dir)
            if result == "ok":
                notify("watchdoc", f"Done \u2014 {path.name}")


def watch_folder(folder: Path, output_dir: Path | None = None) -> None:
    handler = _PDFHandler(output_dir)
    observer = Observer()
    observer.schedule(handler, str(folder), recursive=False)
    observer.start()
    console.print(f"\n[bold]watchdoc[/bold] watching [cyan]{folder}[/cyan]")
    console.print("[dim]waiting for new PDFs\u2026  ctrl-c to stop[/dim]\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[dim]stopping\u2026[/dim]")
    finally:
        observer.stop()
        observer.join()


def _suppress_ocrmypdf_logging() -> None:
    logging.getLogger("ocrmypdf").setLevel(logging.ERROR)
    logging.getLogger("ocrmypdf._exec").setLevel(logging.ERROR)
    logging.getLogger("ocrmypdf._pipeline").setLevel(logging.ERROR)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="watchdoc",
        description="OCR PDFs for Spotlight indexing",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Process existing PDFs in a folder and exit")
    run_p.add_argument("folder", type=Path, help="Folder containing PDFs")
    run_p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write OCR'd copies here instead of in-place",
    )

    watch_p = sub.add_parser("watch", help="Watch a folder and OCR new PDFs as they arrive")
    watch_p.add_argument("folder", type=Path, help="Folder to watch")
    watch_p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write OCR'd copies here instead of in-place",
    )

    inst_p = sub.add_parser("install", help="Install launchd agent for a folder")
    inst_p.add_argument("folder", type=Path, help="Folder to watch")

    sub.add_parser("uninstall", help="Remove launchd agent")

    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    _suppress_ocrmypdf_logging()

    if args.command == "run":
        folder = args.folder.expanduser().resolve()
        if not folder.is_dir():
            parser.error(f"not a directory: {folder}")
        output_dir = None
        if args.output_dir:
            output_dir = args.output_dir.expanduser().resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
        process_folder(folder, output_dir)

    elif args.command == "watch":
        folder = args.folder.expanduser().resolve()
        if not folder.is_dir():
            parser.error(f"not a directory: {folder}")
        output_dir = None
        if args.output_dir:
            output_dir = args.output_dir.expanduser().resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
        watch_folder(folder, output_dir)

    elif args.command == "install":
        folder = args.folder.expanduser().resolve()
        if not folder.is_dir():
            parser.error(f"not a directory: {folder}")
        install(folder)

    elif args.command == "uninstall":
        uninstall()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
