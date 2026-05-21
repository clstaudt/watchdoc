#!/usr/bin/env bash
set -euo pipefail

echo "Installing watchdoc..."

# Homebrew
if ! command -v brew &>/dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# uv
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# System dependencies
echo "Installing system dependencies..."
brew install tesseract ghostscript terminal-notifier

# watchdoc
echo "Installing watchdoc..."
uv tool install git+https://github.com/clstaudt/watchdoc.git

# Ensure ~/.local/bin is on PATH
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo ""
    echo "Add ~/.local/bin to your PATH:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
    echo "  source ~/.zshrc"
fi

echo ""
echo "Done! Run 'watchdoc --help' to get started."
