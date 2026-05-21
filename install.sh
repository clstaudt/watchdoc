#!/usr/bin/env bash
set -euo pipefail

echo "Installing watchdoc..."

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo "Error: Homebrew is required. Install it from https://brew.sh"
    exit 1
fi

# Check for uv
if ! command -v uv &>/dev/null; then
    echo "Error: uv is required. Install it from https://docs.astral.sh/uv/"
    exit 1
fi

# System dependencies
echo "Installing system dependencies..."
brew install tesseract ghostscript terminal-notifier

# Python tool
echo "Installing watchdoc..."
uv tool install git+https://github.com/clstaudt/watchdoc.git

echo ""
echo "Done! Run 'watchdoc --help' to get started."
