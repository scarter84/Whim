"""
Whim Terminal Configuration.
Loads user-specific settings from ~/.openclaw/whim_config.json (or platform equivalent).
Falls back to sensible defaults so the app runs out-of-the-box.
"""

import json
import os
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

HOME = os.path.expanduser("~")


def _config_dir():
    if IS_WINDOWS:
        return os.path.join(
            os.environ.get("APPDATA", os.path.join(HOME, "AppData", "Roaming")),
            "OpenClaw")
    if IS_MAC:
        return os.path.join(HOME, "Library", "Application Support", "OpenClaw")
    return os.path.join(HOME, ".openclaw")


CONFIG_DIR = _config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "whim_config.json")

_DEFAULTS = {
    "vps_host": "",
    "vps_tunnel_port": 8089,
    "tailscale_ip": "",
    "devices": [
        {"name": "localhost", "ip": "127.0.0.1", "label": "PC", "adb_model": None},
    ],
    "default_models": [
        "llama3.1:8b-16k",
        "llama3.1:8b",
        "deepseek-r1:32b",
    ],
    "ollama_host": "http://127.0.0.1:11434",
    "ws_url": "ws://127.0.0.1:18789",
    "ws_token": "",
    "ingest_port": 8088,
    "ss_port": 8091,
    "signal_desktop_bin": "",
    "discord_desktop_bin": "",
}


def load_config():
    cfg = dict(_DEFAULTS)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                user = json.load(f)
            cfg.update(user)
        except Exception:
            pass
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


CONFIG = load_config()
