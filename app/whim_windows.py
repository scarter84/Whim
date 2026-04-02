#!/usr/bin/env python3
"""
Whim Terminal — Windows 11 Launcher

This is the entry point for running Whim Terminal on Windows 11.
It patches platform-specific paths and behaviours before launching
the main openclaw_tkui application.

Requirements:
    pip install -r requirements_windows.txt
    Ollama for Windows must be installed (https://ollama.com/download/windows)

Usage:
    python whim_windows.py
"""

import os
import sys
import ctypes
import platform

# ── Verify we're on Windows ──
if sys.platform != "win32":
    print("This launcher is for Windows only. On Linux, run openclaw_tkui.py directly.")
    sys.exit(1)

# ── Set DPI awareness for crisp rendering on Windows 11 ──
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ── Import and apply platform compatibility ──
from platform_compat import PATHS, IS_WINDOWS, ensure_directories, platform_summary

# Create required directories on first run
ensure_directories()

# ── Patch environment for Whim on Windows ──
# Set OLLAMA_HOST if not already set
if "OLLAMA_HOST" not in os.environ:
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:11434"

# ── Override path constants before importing the main app ──
# We'll monkey-patch the module-level constants after import
import importlib.util

# Store original xdg-open calls will be replaced by os.startfile via platform_compat
print("=" * 60)
print("  Whim Terminal — Windows 11")
print(f"  Python {platform.python_version()} | {platform.machine()}")
print(f"  OS: Windows {platform.release()} ({platform.version()})")
print("=" * 60)
print()

# Check Ollama availability
import urllib.request
try:
    req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=3) as resp:
        print("[OK] Ollama is running")
except Exception:
    print("[!!] Ollama not detected at localhost:11434")
    print("     Install from: https://ollama.com/download/windows")
    print("     Whim will start but AI features will be unavailable.")
    print()

# ── Now import and patch the main module ──
spec = importlib.util.spec_from_file_location(
    "openclaw_tkui",
    os.path.join(os.path.dirname(__file__), "openclaw_tkui.py"))
mod = importlib.util.module_from_spec(spec)

# Inject platform-aware path overrides before exec
mod.JOURNAL_DIR = PATHS["journal_dir"]
mod.ARCHIVE_DIR = PATHS["archive_dir"]
mod.TRANSCRIPT_DIR = PATHS["transcript_dir"]
mod.TABLE_READS_DIR = PATHS["table_reads_dir"]
mod.AUDIO_CAPTURE_DIR = PATHS["audio_capture_dir"]
mod.OPENCLAW_CONFIG = PATHS["openclaw_config"]
mod.WHIM_SETTINGS_FILE = PATHS["whim_settings"]
mod.VOICE_ENGINE_CONFIG = PATHS["voice_engine_cfg"]
mod.SESSIONS_STORE = PATHS["sessions_store"]
mod.WHIM_FONTS_DIR = PATHS["fonts_dir"]
mod.PERSONA_DIR = PATHS["persona_dir"]
mod.PERSONA_CONFIG = PATHS["persona_config"]
mod.XTTS_VOICES_DIR = PATHS["voices_dir"]
mod.LOGO_PATH = PATHS["logo_path"]
mod.SETTINGS_ICON_PATH = PATHS["settings_icon"]
mod.SIGNAL_CONFIG_DIR = PATHS["signal_config_dir"]
mod.SIGNAL_LOG_FILE = PATHS["signal_log_file"]
mod.DISCORD_CONFIG_DIR = PATHS["discord_config_dir"]
mod.SIGNAL_DESKTOP_BIN = PATHS["signal_desktop_bin"]
mod.DISCORD_DESKTOP_BIN = PATHS["discord_desktop_bin"]
mod.XTTS_CONDA_PYTHON = PATHS["xtts_conda_python"]

sys.modules["openclaw_tkui"] = mod

print("[OK] Launching Whim Terminal...")
print()

try:
    spec.loader.exec_module(mod)
except SystemExit:
    pass
except Exception as e:
    print(f"\n[ERROR] Failed to launch: {e}")
    import traceback
    traceback.print_exc()
    input("\nPress Enter to exit...")
