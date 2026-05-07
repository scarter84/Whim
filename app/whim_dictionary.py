"""
Whim Terminal Dictionary — canonical glossary of Whim ecosystem terms.
Used by Whim.ai to maintain consistent terminology and contextual awareness.
"""

WHIM_DICTIONARY = {
    # Core Application
    "Whim Terminal": "The primary desktop application (Tkinter-based) that serves as the unified "
                     "command center for AI, device management, communication, and system "
                     "administration. Built on Linux Mint Cinnamon. Main file: openclaw_tkui.py.",
    "Whim": "The overarching ecosystem/project name encompassing the terminal app, mobile "
            "companion (Whim.m), web presence (whimgo.io), and all integrated services.",
    "OpenClaw": "The AI agent platform that powers Whim's autonomous capabilities. Whim Terminal "
                "acts as the OpenClaw operator client, connecting via WebSocket to the gateway.",
    "WISP": "Whim's Integrated Systems Processor — the resident AI personality/droid that "
            "reviews terminal internals, browses vaults, diagnoses issues, and performs "
            "system tasks. Connected to OpenClaw via Ollama.",
    "Whim.ai": "The local AI chat interface embedded in Whim Terminal, powered by Ollama "
               "(llama3.1 by default). Supports slash commands, presets, streaming, context "
               "metering, and cloud fallback routing.",
    "Whim.m": "The mobile companion script/app deployed to Android devices via ADB. Handles "
              "remote sync, notification forwarding, and device management.",

    # AI & Models
    "Ollama": "The local LLM inference server running on the host machine. Default endpoint: "
              "http://localhost:11434. Hosts models like llama3.1, deepseek-r1, qwen2.5.",
    "Presets": "Named AI configuration profiles in Whim.ai (Default, Creative, Code, Analyst). "
               "Each defines model, context window, temperature, tool access, and system prompt.",
    "OpenTailor": "The Tool Store system within Whim Terminal settings that manages capability "
                  "bundles for each AI preset.",
    "Sovereign Mode": "A toggle in settings that restricts Whim.ai to local-only inference — "
                      "no cloud API fallback (Anthropic, OpenAI, DeepSeek) is attempted.",
    "FreshTail": "The context window management system that builds optimized message history "
                 "for Ollama, handling overflow, token counting, and message prioritization.",
    "GBrain": "An open-source AI memory system (github.com/garrytan/gbrain) that gives AI "
              "agents persistent, structured long-term memory. Uses PGLite/pgvector for "
              "hybrid search, self-wiring knowledge graph, and 34+ skills. Installed at "
              "~/gbrain with brain data at ~/.gbrain/brain.pglite.",

    # Communication
    "Signal": "Signal Messenger integration — desktop app control and signal-cli for "
              "programmatic messaging. Config stored in ~/.config/Signal.",
    "Discord": "Discord desktop integration for messaging and community management.",
    "Himalaya": "CLI email client integrated into Whim.ai for reading, searching, and "
                "managing email directly from the terminal.",

    # Subsystems
    "OpenFang": "The visual watchdog kernel that monitors system state via screenshots, OCR, "
                "and neural analysis. Produces 'kickbacks' when issues are detected. "
                "Commands: /openfang, /chk, /solve.",
    "Collar": "Device management and ADB bridge subsystem. Handles phone/tablet connectivity, "
              "file push/pull, app deployment, and screen mirroring.",
    "TRV": "Transcription and Recording Vault — captures, stores, and plays back audio "
           "recordings and voice notes.",
    "Table Reads": "A feature for reading and processing structured documents, stored in ~/TableReads.",
    "Journal Ingest": "Automated ingestion of journal entries from ~/Journal. Can auto-start "
                      "on launch via settings.",
    "Archive Agent": "An autonomous subsystem that manages the ~/ARCHIVE directory. Supports "
                     "/arc list, /arc read, /arc speak, /arc search commands for retrieval.",

    # Infrastructure
    "Control Panel": "A separate Windows-2000-style settings hub (control_panel.py) for "
                     "Linux Mint Cinnamon system preferences — display, sound, network, etc.",
    "Gateway": "The OpenClaw WebSocket gateway (default ws://127.0.0.1:18789) that bridges "
               "the terminal to agent sessions.",
    "Tunnel": "SSH/reverse tunnel setup for remote device access through a VPS. Monitored "
              "for health via the auto-tunnel-check setting.",
    "Tailscale": "VPN mesh network used for secure device-to-device communication.",

    # Storage & Data
    "Vaults": "The primary user data store at ~/vaults. Contains personal documents, "
              "notes, configuration, and project files.",
    "CLONE_ROOT": "Directory at ~/vaults/CLONE_ROOT containing cloned repositories and "
                  "reference data (meritclaw_data, profiles, README).",
    "Incoming": "A monitored folder for incoming files — downloads, device syncs, etc.",
    "ARCHIVE": "Long-term document storage at ~/ARCHIVE. Managed by the Archive Agent.",
    "Sessions Store": "Persistent storage for OpenClaw session transcripts and state.",

    # Build & Deployment
    "CARRARAmint": "The hostname of the primary development/deployment machine running "
                   "Linux Mint Cinnamon.",
    "Azure Theme": "The Azure-ttk-theme used for Tkinter/ttk widget styling in Whim Terminal.",
    "ADB": "Android Debug Bridge — used extensively for device management, app deployment, "
           "and file transfer to/from Android devices.",
    "whimgo.io": "The Whim project's web presence/site. Repo: github.com/scarter84/whimgo.io.",

    # Configuration
    "whim_settings.json": "Primary settings file at ~/.openclaw/whim_settings.json. Stores "
                          "model selection, API keys, preferences, and feature toggles.",
    "whim_config.json": "Secondary config at ~/.openclaw/whim_config.json. Stores VPS host, "
                        "device definitions, default models, and service endpoints.",
    "openclaw.json": "OpenClaw gateway configuration file.",
    "Voice Engine Config": "Configuration for TTS/voice synthesis features.",
    "Persona": "Customizable AI personality profiles stored in the persona directory.",

    # GitHub Repositories
    "Whim GitHub": "The main Whim Terminal repository at github.com/scarter84/Whim (local: "
                   "~/whim-terminal).",
    "whimgo.io GitHub": "The Whim website repository at github.com/scarter84/whimgo.io "
                        "(local: ~/whimgo.io-site).",
    "0411 GitHub": "Project archive repository at github.com/scarter84/0411 (local: ~/0411).",
    "mtkclient": "MediaTek USB client tool at github.com/bkerler/mtkclient (local: ~/mtkclient).",
}

GITHUB_REPOS = {
    "whim-terminal": {
        "local_path": "/home/tommymunro/whim-terminal",
        "remote": "git@github.com:scarter84/Whim.git",
        "description": "Main Whim Terminal application repository",
    },
    "whimgo.io-site": {
        "local_path": "/home/tommymunro/whimgo.io-site",
        "remote": "https://github.com/scarter84/whimgo.io.git",
        "description": "Whim project website",
    },
    "0411": {
        "local_path": "/home/tommymunro/0411",
        "remote": "git@github.com:scarter84/0411.git",
        "description": "Project archive and reference repo",
    },
    "mtkclient": {
        "local_path": "/home/tommymunro/mtkclient",
        "remote": "https://github.com/bkerler/mtkclient.git",
        "description": "MediaTek USB client tool",
    },
    "Azure-ttk-theme": {
        "local_path": "/home/tommymunro/Azure-ttk-theme",
        "remote": "https://github.com/rdbende/Azure-ttk-theme.git",
        "description": "Tkinter theme used by Whim Terminal",
    },
    "gbrain": {
        "local_path": "/home/tommymunro/gbrain",
        "remote": "https://github.com/garrytan/gbrain.git",
        "description": "AI agent memory system with persistent knowledge graph",
    },
}

GBRAIN_CONFIG_DEFAULTS = {
    "enabled": False,
    "brain_dir": "/home/tommymunro/.gbrain",
    "install_dir": "/home/tommymunro/gbrain",
    "auto_sync": False,
    "mcp_serve": False,
    "import_journal": False,
    "import_vaults": False,
}


def build_whimai_context_block():
    """Build a context string for the Whim.ai system prompt with dictionary + repo awareness."""
    lines = [
        "## Whim Ecosystem Context",
        "You have access to the Whim Terminal dictionary for terminology reference.",
        "Key terms: " + ", ".join(sorted(WHIM_DICTIONARY.keys())[:20]) + ", and more.",
        "",
        "## Local GitHub Repositories",
    ]
    for name, info in GITHUB_REPOS.items():
        lines.append(f"- {name}: {info['local_path']} ({info['description']})")
    lines.append("")
    lines.append("## GBrain Integration")
    lines.append("GBrain (AI agent memory) is installed at ~/gbrain with brain data at ~/.gbrain/.")
    lines.append("Use `gbrain query <question>` for knowledge retrieval, "
                 "`gbrain search <term>` for keyword search, "
                 "`gbrain get <slug>` to read a brain page.")
    return "\n".join(lines)
