from __future__ import annotations

import argparse
import logging
import os
import queue
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import ocrmypdf
from rich.console import Console
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from watchdoc.launchd import check_deps, install, uninstall
from watchdoc.notify import notify

console = Console()


def _process_pdf(path: Path, output_dir: Path | None, *, jobs: int = 0) -> tuple[str, str]:
    """OCR a single PDF. Returns (status, message)."""
    if output_dir:
        target = output_dir / path.name
        tmp = None
    else:
        tmp = path.with_suffix(".pdf.tmp")
        target = tmp

    kwargs: dict = dict(skip_text=True, progress_bar=False)
    if jobs:
        kwargs["jobs"] = jobs

    try:
        result = ocrmypdf.ocr(path, target, **kwargs)
    except Exception as exc:
        if tmp and tmp.exists():
            tmp.unlink()
        return "fail", str(exc)

    if result == ocrmypdf.ExitCode.ok:
        if tmp:
            tmp.replace(path)
        return "ok", ""

    if result == ocrmypdf.ExitCode.already_done_ocr:
        if tmp and tmp.exists():
            tmp.unlink()
        return "skip", ""

    if tmp and tmp.exists():
        tmp.unlink()
    return "fail", str(result)


def _run_one(pdf: Path, output_dir: Path | None) -> tuple[str, str, str]:
    """Returns (status, filename, error_message)."""
    _suppress_ocrmypdf_logging()
    if not pdf.exists():
        return "skip", pdf.name, ""
    status, msg = _process_pdf(pdf, output_dir, jobs=1)
    return status, pdf.name, msg


def process_folder(folder: Path, output_dir: Path | None = None) -> None:
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        return

    workers = min(len(pdfs), os.cpu_count() or 4)
    console.print(f"\n[bold]Processing {len(pdfs)} PDF(s)[/bold] in {folder}  [dim]({workers} workers)[/dim]\n")

    counts: dict[str, int] = {"ok": 0, "skip": 0, "fail": 0}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_one, pdf, output_dir) for pdf in pdfs]
        for future in as_completed(futures):
            try:
                status, name, msg = future.result()
            except Exception as exc:
                console.print(f"  [red]x[/red] [dim]{exc}[/dim]")
                counts["fail"] += 1
                continue
            counts[status] += 1
            if status == "ok":
                console.print(f"  [green]\u2713[/green] {name}")
            elif status == "fail":
                console.print(f"  [red]x[/red] {name}  [dim]{msg}[/dim]")

    if counts["ok"] or counts["fail"]:
        parts = []
        if counts["ok"]:
            parts.append(f"[green]{counts['ok']} indexed[/green]")
        if counts["fail"]:
            parts.append(f"[red]{counts['fail']} failed[/red]")
        summary = ", ".join(parts)
        console.print(f"\n[bold]Done[/bold] \u2014 {summary}\n")

        nparts = []
        if counts["ok"]:
            nparts.append(f"{counts['ok']} indexed")
        if counts["fail"]:
            nparts.append(f"{counts['fail']} failed")
        notify("watchdoc", ", ".join(nparts))
    elif counts["skip"]:
        console.print(f"\n[dim]nothing new to OCR[/dim]\n")


class _PDFHandler(FileSystemEventHandler):

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
            try:
                console.print(f"\n[bold cyan]\u25cf[/bold cyan] [bold]{path.name}[/bold] detected")
                time.sleep(2)
                if not path.exists():
                    console.print("  [dim]file disappeared, skipping[/dim]")
                    continue
                status, msg = _process_pdf(path, self._output_dir)
                if status == "ok":
                    console.print(f"  [green]\u2713[/green] {path.name}")
                    notify("watchdoc", f"{path.name} indexed")
                elif status == "fail":
                    console.print(f"  [red]x[/red] {path.name}  [dim]{msg}[/dim]")
                    notify("watchdoc", f"{path.name} failed")
            except Exception as exc:
                console.print(f"  [red]x[/red] {path.name}  [dim]{exc}[/dim]")
                notify("watchdoc", f"{path.name} failed")


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

    run_p = sub.add_parser("run", help="Process all PDFs in a folder and exit")
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
    sub.add_parser("deps", help="Check system dependencies")

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

    elif args.command == "deps":
        check_deps()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
