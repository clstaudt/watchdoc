#!/usr/bin/env bash
set -euo pipefail

echo "Installing watchdoc..."

# Homebrew
if ! command -v brew &>/dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# uv (its installer adds ~/.local/bin to PATH)
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env"
fi

# System dependencies
echo "Installing system dependencies..."
brew install tesseract ghostscript terminal-notifier

# watchdoc
echo "Installing watchdoc..."
uv tool install git+https://github.com/clstaudt/watchdoc.git

echo ""
echo "Done! Run 'watchdoc --help' to get started."
