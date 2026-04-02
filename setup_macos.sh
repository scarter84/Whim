#!/usr/bin/env bash
set -euo pipefail

echo "=== Whim Terminal — macOS Setup ==="

# Check Python version
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10+ is required. Install via:"
    echo "  brew install python@3.12"
    exit 1
fi

echo "Using: $PYTHON ($($PYTHON --version))"

# Check Tcl/Tk
$PYTHON -c "import tkinter; print('Tkinter OK:', tkinter.TkVersion)" 2>/dev/null || {
    echo "Error: Tkinter not available. Install Python with Tk support:"
    echo "  brew install python-tk@3.12"
    exit 1
}

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv venv
fi

echo "Installing dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# Create application directories
APP_SUPPORT="$HOME/Library/Application Support/OpenClaw"
WHIM_DOCS="$HOME/Documents/Whim"
mkdir -p "$APP_SUPPORT"
mkdir -p "$WHIM_DOCS/Journal/audio_captures"
mkdir -p "$WHIM_DOCS/ARCHIVE"
mkdir -p "$WHIM_DOCS/TRANSCRIPT"
mkdir -p "$WHIM_DOCS/TableReads"
mkdir -p "$WHIM_DOCS/Incoming"
mkdir -p "$WHIM_DOCS/voices/personas"

# Copy config template if no config exists
if [ ! -f "$APP_SUPPORT/whim_config.json" ]; then
    cp config.template.json "$APP_SUPPORT/whim_config.json"
    echo "Created config at: $APP_SUPPORT/whim_config.json"
    echo "  Edit this file to configure VPS, devices, and models."
fi

echo ""
echo "=== Setup Complete ==="
echo "Run Whim Terminal with:"
echo "  venv/bin/python openclaw_tkui.py"
echo ""
echo "Optional: Install Ollama for local AI:"
echo "  brew install ollama"
