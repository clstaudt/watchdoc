<p align="center">
  <img src="logo.png" width="200" alt="watchdoc logo — a dog fetching a document" style="border-radius: 24px;">
</p>

<h1 align="center">watchdoc</h1>

<p align="center">
  Watch a folder for PDFs and run OCR so Spotlight can index them.
</p>

---

Scanned PDFs are just images — Spotlight can't search their text. **watchdoc** runs [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) on them automatically, adding a searchable text layer in-place.

## Install

Requires [Homebrew](https://brew.sh) and [uv](https://docs.astral.sh/uv/).

```bash
curl -fsSL https://raw.githubusercontent.com/clstaudt/watchdoc/main/install.sh | sh
```

This installs the system dependencies (`tesseract`, `ghostscript`, `terminal-notifier`) and the `watchdoc` CLI in one step.

## Usage

### One-shot: process existing PDFs

```bash
watchdoc run ~/Documents/Scans
```

Processes all `*.pdf` files in parallel (one per CPU core), then exits.

### Watch mode: process new PDFs as they arrive

```bash
watchdoc watch ~/Documents/Scans
```

Stays running and OCRs each new PDF dropped into the folder. Stop with `ctrl-c`.

### Persistent: install as a launchd agent

```bash
watchdoc install ~/Documents/Scans
```

Installs a macOS launch agent that triggers automatically whenever the folder contents change.

```bash
watchdoc uninstall
```

Removes the launch agent.

### Options

| Flag | Commands | Description |
|------|----------|-------------|
| `--output-dir DIR` | `run`, `watch` | Write OCR'd copies to a separate folder instead of replacing in-place |

## System dependencies

```bash
brew install tesseract ghostscript terminal-notifier
```

Check what's missing with:

```bash
watchdoc deps
```

- **tesseract** — OCR engine
- **ghostscript** — PDF rasterizer
- **terminal-notifier** — optional, shows a notification with the watchdoc icon when processing completes

## How it works

```
PDF added to folder
        │
        ▼
   watchdoc run
        │
        ▼
  ocrmypdf (mode=redo)
        │
  ┌─────┴─────┐
  │ tesseract  │  ← extracts text from page images
  │ghostscript │  ← rasterizes PDF pages
  └─────┬─────┘
        │
        ▼
  PDF with text layer
        │
        ▼
  Spotlight indexes it
```

## License

MIT
