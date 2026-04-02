# Whim Terminal

A cross-platform AI terminal interface built with Python and Tkinter. Connects to local Ollama models for AI chat, voice synthesis, device management, multi-terminal sync, and more.

## Features

- **AI Chat** — Talk to local LLMs via Ollama (llama3, deepseek, qwen, etc.)
- **Voice Engine** — Text-to-speech with XTTS v2 and persona management
- **Multi-Terminal Sync** — 7 sync approaches: WebSocket, VPS rsync, CRDT, Git, Hybrid, Session Mirror, Phone Bridge
- **SmartThings Integration** — Control smart home devices
- **Signal & Discord** — Messaging integration
- **Library Browser** — Browse and manage local files
- **Audio Capture** — System audio recording
- **Device Management** — ADB device portal, device status monitoring

## Supported Platforms

- **Linux** (primary development platform)
- **macOS Tahoe** (15.x+)
- **Windows 11** (via `whim_windows.py` launcher)

## Quick Start

### macOS

```bash
git clone https://github.com/YOUR_USERNAME/whim-terminal.git
cd whim-terminal
chmod +x setup_macos.sh
./setup_macos.sh
venv/bin/python openclaw_tkui.py
```

### Linux

```bash
git clone https://github.com/YOUR_USERNAME/whim-terminal.git
cd whim-terminal
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python openclaw_tkui.py
```

### Windows

```powershell
git clone https://github.com/YOUR_USERNAME/whim-terminal.git
cd whim-terminal
python -m venv venv
venv\Scripts\pip install -r requirements.txt
python whim_windows.py
```

## Configuration

On first run, copy `config.template.json` to your platform's config directory:

| Platform | Config Path |
|----------|-------------|
| Linux | `~/.openclaw/whim_config.json` |
| macOS | `~/Library/Application Support/OpenClaw/whim_config.json` |
| Windows | `%APPDATA%\OpenClaw\whim_config.json` |

Edit the config to set your VPS host, devices, default models, and other preferences.

## Dependencies

- Python 3.10+
- Tkinter (usually bundled with Python)
- [Ollama](https://ollama.ai/) for local AI models

See `requirements.txt` for Python packages.

## Architecture

| File | Purpose |
|------|---------|
| `openclaw_tkui.py` | Main application UI |
| `platform_compat.py` | Cross-platform abstraction layer |
| `whim_config.py` | User configuration loader |
| `whim_sync.py` | Multi-terminal sync engine |
| `whim_windows.py` | Windows-specific launcher |
| `control_panel.py` | System control panel (Linux) |

## License

MIT
