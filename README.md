# Whim Terminal

A cross-platform AI terminal interface built with Python and Tkinter. Connects to local Ollama models for AI chat, voice synthesis, device management, multi-terminal sync, persistent AI memory, and more. 20 module tabs, fully sovereign, no cloud required.

## Features

- **AI Chat (Whim.ai)** — Local LLM chat via Ollama (DeepSeek R1:32B, Llama 3.1:8B, Qwen). Presets, observability panel, context metering, cloud fallback routing, and GBrain knowledge retrieval
- **BRAIN (GBrain Integration)** — Persistent AI memory with PGLite/pgvector. Natural language search, Entity Explorer (People/Companies/Devices/Projects/Locations), Timeline View, Dream Cycle scheduler, backlink visualization, Obsidian-compatible export. Ctrl+Shift+G quick-query from any tab
- **Whim Dictionary** — 43-term ecosystem glossary injected into AI system prompts. GitHub repo awareness, subsystem context, and GBrain integration
- **Voice Engine** — Text-to-speech with XTTS v2 and persona management
- **Multi-Terminal Sync** — 7 sync approaches: WebSocket, VPS rsync, CRDT, Git, Hybrid, Session Mirror, Phone Bridge
- **SmartThings Integration** — Control smart home devices
- **Signal & Discord** — Messaging integration
- **Email (Himalaya)** — CLI email client with IMAP/SMTP, integrated into Whim.ai chat
- **Library Browser** — Browse and manage local files
- **Audio Capture** — System audio recording
- **Device Management** — ADB device portal, device status monitoring
- **OpenFang** — Visual watchdog kernel with OCR and neural analysis
- **Archive Agent** — Autonomous document retrieval from ~/ARCHIVE
- **Doppler** — Weather radar with NEXRAD overlay
- **GeoF** — Geofence tracker with LoRa bridge
- **HAM** — APRS amateur radio monitor
- **NodeFlow** — Visual node-based flow editor for droid and data pipelines

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
| `openclaw_tkui.py` | Main application UI (22K+ lines, 20 tabs) |
| `whim_dictionary.py` | Ecosystem glossary + GitHub repo registry + GBrain context |
| `platform_compat.py` | Cross-platform abstraction layer |
| `whim_config.py` | User configuration loader |
| `whim_sync.py` | Multi-terminal sync engine |
| `whim_windows.py` | Windows-specific launcher |
| `control_panel.py` | System control panel (Linux) |

## License

MIT
