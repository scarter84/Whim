"""
Platform compatibility layer for Whim Terminal.
Abstracts OS-specific calls so the same codebase runs on Linux, macOS, and Windows.
"""

import os
import sys
import subprocess
import platform
import shutil

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

HOME = os.path.expanduser("~")


# ── Path Defaults ──

def _win_appdata():
    return os.environ.get("APPDATA", os.path.join(HOME, "AppData", "Roaming"))

def _win_localappdata():
    return os.environ.get("LOCALAPPDATA", os.path.join(HOME, "AppData", "Local"))

def _mac_app_support():
    return os.path.join(HOME, "Library", "Application Support")

def default_paths():
    if IS_WINDOWS:
        openclaw_dir = os.path.join(_win_appdata(), "OpenClaw")
        return {
            "openclaw_dir":      openclaw_dir,
            "openclaw_config":   os.path.join(openclaw_dir, "openclaw.json"),
            "whim_settings":     os.path.join(openclaw_dir, "whim_settings.json"),
            "voice_engine_cfg":  os.path.join(openclaw_dir, "voice_engine.json"),
            "sessions_store":    os.path.join(openclaw_dir, "whim_sessions.json"),
            "whim_icon":         os.path.join(openclaw_dir, "Whim.png"),
            "fonts_dir":         os.path.join(openclaw_dir, "WhimUI", "fonts"),
            "journal_dir":       os.path.join(HOME, "Documents", "Whim", "Journal"),
            "archive_dir":       os.path.join(HOME, "Documents", "Whim", "ARCHIVE"),
            "transcript_dir":    os.path.join(HOME, "Documents", "Whim", "TRANSCRIPT"),
            "table_reads_dir":   os.path.join(HOME, "Documents", "Whim", "TableReads"),
            "audio_capture_dir": os.path.join(HOME, "Documents", "Whim", "Journal", "audio_captures"),
            "voices_dir":        os.path.join(HOME, "Documents", "Whim", "voices"),
            "persona_dir":       os.path.join(HOME, "Documents", "Whim", "voices", "personas"),
            "persona_config":    os.path.join(HOME, "Documents", "Whim", "voices", "personas", "personas.json"),
            "incoming_dir":      os.path.join(HOME, "Documents", "Whim", "Incoming"),
            "downloads_dir":     os.path.join(HOME, "Downloads"),
            "logo_path":         os.path.join(HOME, "Documents", "Whim", "Incoming", "fire.png"),
            "settings_icon":     os.path.join(HOME, "Documents", "Whim", "settings.png"),
            "signal_config_dir": os.path.join(_win_appdata(), "Signal"),
            "signal_log_file":   os.path.join(_win_appdata(), "Signal", "logs", "main.log"),
            "discord_config_dir":os.path.join(_win_appdata(), "discord"),
            "xtts_conda_python": "python",
            "signal_desktop_bin":"",
            "discord_desktop_bin":"",
        }
    elif IS_MAC:
        openclaw_dir = os.path.join(_mac_app_support(), "OpenClaw")
        return {
            "openclaw_dir":      openclaw_dir,
            "openclaw_config":   os.path.join(openclaw_dir, "openclaw.json"),
            "whim_settings":     os.path.join(openclaw_dir, "whim_settings.json"),
            "voice_engine_cfg":  os.path.join(openclaw_dir, "voice_engine.json"),
            "sessions_store":    os.path.join(openclaw_dir, "whim_sessions.json"),
            "whim_icon":         os.path.join(openclaw_dir, "Whim.png"),
            "fonts_dir":         os.path.join(openclaw_dir, "WhimUI", "fonts"),
            "journal_dir":       os.path.join(HOME, "Documents", "Whim", "Journal"),
            "archive_dir":       os.path.join(HOME, "Documents", "Whim", "ARCHIVE"),
            "transcript_dir":    os.path.join(HOME, "Documents", "Whim", "TRANSCRIPT"),
            "table_reads_dir":   os.path.join(HOME, "Documents", "Whim", "TableReads"),
            "audio_capture_dir": os.path.join(HOME, "Documents", "Whim", "Journal", "audio_captures"),
            "voices_dir":        os.path.join(HOME, "Documents", "Whim", "voices"),
            "persona_dir":       os.path.join(HOME, "Documents", "Whim", "voices", "personas"),
            "persona_config":    os.path.join(HOME, "Documents", "Whim", "voices", "personas", "personas.json"),
            "incoming_dir":      os.path.join(HOME, "Documents", "Whim", "Incoming"),
            "downloads_dir":     os.path.join(HOME, "Downloads"),
            "logo_path":         os.path.join(HOME, "Documents", "Whim", "Incoming", "fire.png"),
            "settings_icon":     os.path.join(HOME, "Documents", "Whim", "settings.png"),
            "signal_config_dir": os.path.join(_mac_app_support(), "Signal"),
            "signal_log_file":   os.path.join(HOME, "Library", "Logs", "Signal", "main.log"),
            "discord_config_dir":os.path.join(_mac_app_support(), "discord"),
            "xtts_conda_python": os.path.join(HOME, "miniconda3", "envs", "xtts", "bin", "python"),
            "signal_desktop_bin":"/Applications/Signal.app/Contents/MacOS/Signal",
            "discord_desktop_bin":"/Applications/Discord.app/Contents/MacOS/Discord",
        }
    else:
        openclaw_dir = os.path.expanduser("~/.openclaw")
        return {
            "openclaw_dir":      openclaw_dir,
            "openclaw_config":   os.path.join(openclaw_dir, "openclaw.json"),
            "whim_settings":     os.path.join(openclaw_dir, "whim_settings.json"),
            "voice_engine_cfg":  os.path.join(openclaw_dir, "voice_engine.json"),
            "sessions_store":    os.path.join(openclaw_dir, "whim_sessions.json"),
            "whim_icon":         os.path.join(openclaw_dir, "Whim.png"),
            "fonts_dir":         os.path.join(openclaw_dir, "WhimUI", "fonts"),
            "journal_dir":       os.path.expanduser("~/Journal"),
            "archive_dir":       os.path.expanduser("~/ARCHIVE"),
            "transcript_dir":    os.path.expanduser("~/TRANSCRIPT"),
            "table_reads_dir":   os.path.expanduser("~/TableReads"),
            "audio_capture_dir": os.path.expanduser("~/Journal/audio_captures"),
            "voices_dir":        os.path.expanduser("~/voices"),
            "persona_dir":       os.path.expanduser("~/voices/personas"),
            "persona_config":    os.path.expanduser("~/voices/personas/personas.json"),
            "incoming_dir":      os.path.expanduser("~/Incoming"),
            "downloads_dir":     os.path.expanduser("~/Downloads"),
            "logo_path":         os.path.expanduser("~/Incoming/fire.png"),
            "settings_icon":     os.path.expanduser("~/settings.png"),
            "signal_config_dir": os.path.expanduser("~/.config/Signal"),
            "signal_log_file":   os.path.expanduser("~/.config/Signal/logs/main.log"),
            "discord_config_dir":os.path.expanduser("~/.config/discord"),
            "xtts_conda_python": os.path.expanduser("~/miniconda3/envs/xtts/bin/python"),
            "signal_desktop_bin":"/opt/Signal/signal-desktop",
            "discord_desktop_bin":"/usr/share/discord/Discord",
        }

PATHS = default_paths()


# ── Open File / Folder in System Default ──

def open_file(path):
    if IS_WINDOWS:
        os.startfile(path)
    elif IS_MAC:
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ── Service / Tunnel Status ──

def is_service_active(service_name):
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["sc", "query", service_name],
                capture_output=True, text=True, timeout=5)
            return "RUNNING" in result.stdout
        except Exception:
            return False
    elif IS_MAC:
        try:
            result = subprocess.run(
                ["launchctl", "list", service_name],
                capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True, text=True, timeout=5)
            return result.stdout.strip() == "active"
        except Exception:
            return False


def check_tunnel_status(vps_host, vps_port):
    import socket
    tunnel_up = False
    if IS_WINDOWS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((vps_host, vps_port))
            s.close()
            tunnel_up = True
        except Exception:
            pass
    elif IS_MAC:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((vps_host, vps_port))
            s.close()
            tunnel_up = True
        except Exception:
            pass
    else:
        if is_service_active("whim-tunnel.service"):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((vps_host, vps_port))
                s.close()
                tunnel_up = True
            except Exception:
                pass
    return tunnel_up


# ── Audio Sources (PulseAudio / Windows) ──

def list_audio_monitor_sources():
    if IS_WINDOWS or IS_MAC:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            sources = []
            source_map = {}
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] > 0:
                    label = dev["name"]
                    sources.append(label)
                    source_map[label] = {"index": i, "name": dev["name"]}
            return sources, source_map
        except Exception:
            return [], {}
    else:
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True, text=True, timeout=5)
            sources = []
            source_map = {}
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2 and ".monitor" in parts[1]:
                    name = parts[1]
                    sources.append(name)
                    source_map[name] = {"name": name}
            return sources, source_map
        except Exception:
            return [], {}


def start_audio_capture(source_name, output_path, fmt="mp3"):
    if IS_WINDOWS or IS_MAC:
        try:
            import sounddevice as sd
            import numpy as np
            return {"method": "sounddevice", "source": source_name}
        except ImportError:
            return None
    else:
        codec_map = {
            "mp3": ["-c:a", "libmp3lame", "-b:a", "192k"],
            "opus": ["-c:a", "libopus", "-b:a", "128k"],
            "ogg": ["-c:a", "libvorbis", "-b:a", "192k"],
            "m4a": ["-c:a", "aac", "-b:a", "192k"],
            "wav": ["-c:a", "pcm_s16le"],
        }
        codec_args = codec_map.get(fmt, codec_map["mp3"])
        cmd = [
            "ffmpeg", "-f", "pulse", "-i", source_name,
            *codec_args, "-y", output_path
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"method": "ffmpeg", "process": proc}


# ── Tailscale ──

def tailscale_status():
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=10)
        else:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            return True, data
    except Exception:
        pass
    return False, {}


# ── Ollama ──

def ollama_base_url():
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


def ensure_directories():
    for key, path in PATHS.items():
        if key.endswith("_dir") and not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception:
                pass

def has_rsync():
    if IS_WINDOWS:
        for cmd in ["rsync", "cwrsync"]:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
                return True
            except Exception:
                continue
        return False
    try:
        subprocess.run(["rsync", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

def has_git():
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

def has_ssh():
    try:
        subprocess.run(["ssh", "-V"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


# ── Process Management (cross-platform pgrep/pkill) ──

def is_process_running(name):
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}"],
                capture_output=True, text=True, timeout=5)
            return name.lower() in result.stdout.lower()
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(
                ["pgrep", "-x", name],
                capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False


def is_process_running_pattern(pattern):
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["tasklist"], capture_output=True, text=True, timeout=5)
            return pattern.lower() in result.stdout.lower()
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False


def kill_process(name):
    if IS_WINDOWS:
        try:
            subprocess.run(["taskkill", "/IM", name, "/F"],
                           capture_output=True, timeout=5)
        except Exception:
            pass
    else:
        try:
            subprocess.run(["pkill", "-x", name],
                           capture_output=True, timeout=5)
        except Exception:
            pass


# ── Media Playback (cross-platform ffplay) ──

def play_audio(path):
    if IS_MAC:
        subprocess.Popen(["afplay", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif IS_WINDOWS:
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            subprocess.Popen(["ffplay", "-autoexit", "-nodisp", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["ffplay", "-autoexit", "-nodisp", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def has_ffmpeg():
    return shutil.which("ffmpeg") is not None


def has_ffplay():
    if IS_MAC:
        return shutil.which("afplay") is not None or shutil.which("ffplay") is not None
    return shutil.which("ffplay") is not None


# ── Document Opening ──

def open_document(path):
    if IS_MAC:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".odt", ".doc", ".docx"):
            try:
                subprocess.Popen(["open", "-a", "Pages", path])
                return
            except Exception:
                pass
        subprocess.Popen(["open", path])
    elif IS_WINDOWS:
        os.startfile(path)
    else:
        try:
            subprocess.Popen(["libreoffice", "--writer", path])
        except FileNotFoundError:
            subprocess.Popen(["xdg-open", path])


# ── Disk Usage (cross-platform statvfs) ──

def disk_usage_gb(path=None):
    path = path or HOME
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0}


# ── Font Selection ──

def platform_fonts():
    if IS_MAC:
        return {
            "ui":    "Helvetica Neue",
            "mono":  "Menlo",
            "title": "Helvetica Neue",
            "emoji": "Apple Color Emoji",
        }
    elif IS_WINDOWS:
        return {
            "ui":    "Segoe UI",
            "mono":  "Consolas",
            "title": "Segoe UI",
            "emoji": "Segoe UI Emoji",
        }
    else:
        return {
            "ui":    "Segoe UI",
            "mono":  "Consolas",
            "title": "Segoe UI",
            "emoji": "Noto Color Emoji",
        }


# ── macOS Retina / DPI ──

def configure_dpi(root):
    if IS_MAC:
        try:
            root.tk.call("tk", "scaling", 2.0)
        except Exception:
            pass
    elif IS_WINDOWS:
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


# ── Platform Info (updated) ──

def platform_summary():
    return {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "is_windows": IS_WINDOWS,
        "is_mac": IS_MAC,
        "is_linux": IS_LINUX,
    }


def sync_config_dir():
    if IS_WINDOWS:
        return os.path.join(_win_appdata(), "OpenClaw")
    if IS_MAC:
        return os.path.join(_mac_app_support(), "OpenClaw")
    return os.path.expanduser("~/.openclaw")
