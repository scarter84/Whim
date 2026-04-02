"""
Whim Multi-Terminal Sync Engine
================================
Implements all 7 sync approaches from the architecture document:
  1. WebSocket Sync Daemon (Tailscale real-time)
  2. VPS rsync Fallback
  3. CRDT Live Collaboration
  4. Git-based Sync
  5. Hybrid: Tailscale + VPS Fallback
  6. Multi-Terminal Session Sharing (Mirror)
  7. Phone as Sync Bridge

Cross-platform: works on both Linux and Windows 11.
"""

import asyncio
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# ── Sync Config Defaults ──

SYNC_PORT = 18790
SYNC_HEARTBEAT_INTERVAL = 10
SYNC_FULL_RECONCILE_INTERVAL = 300
SYNC_DEBOUNCE_SECONDS = 2
SYNC_VPS_REMOTE_DIR = "/home/whim_sync"
SYNC_GIT_COMMIT_INTERVAL = 60
MIRROR_PORT = 18791

def _openclaw_dir():
    if IS_WINDOWS:
        base = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"),
                              "AppData", "Roaming"))
        return os.path.join(base, "OpenClaw")
    if IS_MAC:
        return os.path.join(os.path.expanduser("~"), "Library",
                            "Application Support", "OpenClaw")
    return os.path.expanduser("~/.openclaw")

def _default_sync_config_path():
    return os.path.join(_openclaw_dir(), "whim_sync.json")

def _default_sync_state_path():
    return os.path.join(_openclaw_dir(), "whim_sync_state.json")

SYNC_CONFIG_PATH = _default_sync_config_path()
SYNC_STATE_PATH = _default_sync_state_path()


# ======================================================================
#  VECTOR CLOCK — used for last-writer-wins conflict resolution
# ======================================================================

class VectorClock:
    def __init__(self, clocks=None):
        self.clocks = dict(clocks) if clocks else {}

    def increment(self, node_id):
        self.clocks[node_id] = self.clocks.get(node_id, 0) + 1

    def merge(self, other):
        all_keys = set(self.clocks) | set(other.clocks)
        merged = {}
        for k in all_keys:
            merged[k] = max(self.clocks.get(k, 0), other.clocks.get(k, 0))
        self.clocks = merged

    def dominates(self, other):
        if not other.clocks:
            return bool(self.clocks)
        for k in set(self.clocks) | set(other.clocks):
            if self.clocks.get(k, 0) < other.clocks.get(k, 0):
                return False
        return self.clocks != other.clocks

    def to_dict(self):
        return dict(self.clocks)

    @classmethod
    def from_dict(cls, d):
        return cls(d)


# ======================================================================
#  SYNC STATE — tracks per-file metadata across all approaches
# ======================================================================

class SyncState:
    def __init__(self, path=None):
        self.path = path or SYNC_STATE_PATH
        self.node_id = None
        self.files = {}
        self.peers = {}
        self.vector_clock = VectorClock()
        self.local_queue = []
        self.last_vps_sync = None
        self.last_git_sync = None
        self.last_ws_sync = None
        self.mirror_sessions = {}
        self.load()

    def load(self):
        if os.path.isfile(self.path):
            try:
                with open(self.path, "r") as f:
                    data = json.load(f)
                self.node_id = data.get("node_id", str(uuid.uuid4())[:8])
                self.files = data.get("files", {})
                self.peers = data.get("peers", {})
                self.vector_clock = VectorClock.from_dict(data.get("vector_clock", {}))
                self.local_queue = data.get("local_queue", [])
                self.last_vps_sync = data.get("last_vps_sync")
                self.last_git_sync = data.get("last_git_sync")
                self.last_ws_sync = data.get("last_ws_sync")
            except Exception:
                self.node_id = str(uuid.uuid4())[:8]
        else:
            self.node_id = str(uuid.uuid4())[:8]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = {
            "node_id": self.node_id,
            "files": self.files,
            "peers": self.peers,
            "vector_clock": self.vector_clock.to_dict(),
            "local_queue": self.local_queue,
            "last_vps_sync": self.last_vps_sync,
            "last_git_sync": self.last_git_sync,
            "last_ws_sync": self.last_ws_sync,
        }
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def file_hash(self, filepath):
        try:
            with open(filepath, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return None

    def record_file(self, key, filepath):
        h = self.file_hash(filepath)
        mtime = os.path.getmtime(filepath) if os.path.isfile(filepath) else 0
        self.files[key] = {
            "path": filepath,
            "hash": h,
            "mtime": mtime,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        self.vector_clock.increment(self.node_id)

    def has_changed(self, key, filepath):
        if key not in self.files:
            return True
        current_hash = self.file_hash(filepath)
        return current_hash != self.files[key].get("hash")

    def queue_change(self, key, filepath, action="update"):
        self.local_queue.append({
            "key": key,
            "path": filepath,
            "action": action,
            "hash": self.file_hash(filepath),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node_id": self.node_id,
        })

    def drain_queue(self):
        items = list(self.local_queue)
        self.local_queue.clear()
        return items


# ======================================================================
#  SYNC CONFIG — user-facing configuration
# ======================================================================

class SyncConfig:
    DEFAULTS = {
        "enabled": False,
        "mode": "hybrid",
        "node_name": platform.node(),
        "sync_targets": {
            "sessions": True,
            "settings": True,
            "voice_engine": True,
            "device_locations": True,
            "personas": True,
            "journal_manifest": True,
            "archive_text": True,
        },
        "websocket": {
            "enabled": True,
            "port": SYNC_PORT,
            "heartbeat_interval": SYNC_HEARTBEAT_INTERVAL,
            "reconcile_interval": SYNC_FULL_RECONCILE_INTERVAL,
        },
        "vps": {
            "enabled": True,
            "host": "",
            "user": "",
            "remote_dir": SYNC_VPS_REMOTE_DIR,
            "ssh_key": "",
            "auto_push_on_close": True,
            "auto_pull_on_open": True,
        },
        "git": {
            "enabled": False,
            "repo_url": "",
            "branch": "main",
            "auto_commit_interval": SYNC_GIT_COMMIT_INTERVAL,
        },
        "mirror": {
            "enabled": True,
            "port": MIRROR_PORT,
            "allow_control": False,
        },
        "phone_bridge": {
            "enabled": True,
            "relay_port": 8089,
        },
        "never_sync_keys": [
            "api_key", "apiKey", "token", "secret", "password",
        ],
    }

    def __init__(self, path=None):
        self.path = path or SYNC_CONFIG_PATH
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        if os.path.isfile(self.path):
            try:
                with open(self.path, "r") as f:
                    saved = json.load(f)
                self._deep_merge(self.data, saved)
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def _deep_merge(self, base, override):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    def get(self, *keys, default=None):
        d = self.data
        for k in keys:
            if isinstance(d, dict) and k in d:
                d = d[k]
            else:
                return default
        return d


# ======================================================================
#  FILE WATCHER — monitors sync targets for changes
# ======================================================================

class FileWatcher:
    def __init__(self, state, config, on_change_callback=None):
        self.state = state
        self.config = config
        self.callback = on_change_callback
        self._running = False
        self._thread = None
        self._debounce = {}

    def _resolve_targets(self):
        targets = {}
        paths = self._get_sync_paths()
        sync_targets = self.config.get("sync_targets") or {}
        for key, enabled in sync_targets.items():
            if enabled and key in paths:
                p = paths[key]
                if isinstance(p, str):
                    targets[key] = p
                elif isinstance(p, list):
                    for i, pp in enumerate(p):
                        targets[f"{key}:{i}"] = pp
        return targets

    def _get_sync_paths(self):
        oc = _openclaw_dir()
        home = os.path.expanduser("~")
        if IS_WINDOWS:
            whim_data = os.path.join(home, "Documents", "Whim")
        elif IS_MAC:
            whim_data = os.path.join(home, "Documents", "Whim")
        else:
            whim_data = home

        return {
            "sessions": os.path.join(oc, "whim_sessions.json"),
            "settings": os.path.join(oc, "whim_settings.json"),
            "voice_engine": os.path.join(oc, "voice_engine.json"),
            "personas": os.path.join(whim_data, "voices", "personas", "personas.json"),
            "journal_manifest": os.path.join(whim_data, "Journal"),
            "archive_text": os.path.join(whim_data, "ARCHIVE"),
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                targets = self._resolve_targets()
                for key, path in targets.items():
                    if os.path.isdir(path):
                        self._check_directory(key, path)
                    elif os.path.isfile(path):
                        self._check_file(key, path)
            except Exception:
                pass
            time.sleep(SYNC_DEBOUNCE_SECONDS)

    def _check_file(self, key, path):
        if self.state.has_changed(key, path):
            now = time.time()
            last = self._debounce.get(key, 0)
            if now - last < SYNC_DEBOUNCE_SECONDS:
                return
            self._debounce[key] = now
            self.state.record_file(key, path)
            self.state.queue_change(key, path)
            self.state.save()
            if self.callback:
                self.callback(key, path, "update")

    def _check_directory(self, key, dirpath):
        if not os.path.isdir(dirpath):
            return
        for fname in os.listdir(dirpath):
            fpath = os.path.join(dirpath, fname)
            if os.path.isfile(fpath) and fname.endswith((".json", ".txt")):
                fkey = f"{key}:{fname}"
                self._check_file(fkey, fpath)

    def get_sync_paths(self):
        return self._get_sync_paths()


# ======================================================================
#  APPROACH 1: WEBSOCKET SYNC DAEMON (Tailscale real-time)
# ======================================================================

class WebSocketSyncDaemon:
    def __init__(self, state, config, on_remote_update=None):
        self.state = state
        self.config = config
        self.on_remote_update = on_remote_update
        self._running = False
        self._server = None
        self._clients = {}
        self._loop = None
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception:
            pass

    async def _serve(self):
        try:
            import websockets
        except ImportError:
            return

        port = self.config.get("websocket", "port", default=SYNC_PORT)

        async def handler(websocket, path=None):
            peer_id = None
            try:
                async for message in websocket:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "hello":
                        peer_id = data.get("node_id", "unknown")
                        self._clients[peer_id] = websocket
                        self.state.peers[peer_id] = {
                            "name": data.get("node_name", peer_id),
                            "last_seen": datetime.now(timezone.utc).isoformat(),
                            "platform": data.get("platform", "unknown"),
                        }
                        self.state.save()
                        await websocket.send(json.dumps({
                            "type": "hello_ack",
                            "node_id": self.state.node_id,
                            "node_name": self.config.get("node_name", default="unknown"),
                            "platform": sys.platform,
                            "vector_clock": self.state.vector_clock.to_dict(),
                        }))

                    elif msg_type == "heartbeat":
                        if peer_id and peer_id in self.state.peers:
                            self.state.peers[peer_id]["last_seen"] = \
                                datetime.now(timezone.utc).isoformat()
                        await websocket.send(json.dumps({
                            "type": "heartbeat_ack",
                            "node_id": self.state.node_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }))

                    elif msg_type == "sync_push":
                        self._handle_sync_push(data)

                    elif msg_type == "sync_request":
                        response = self._build_sync_response(data)
                        await websocket.send(json.dumps(response))

                    elif msg_type == "reconcile_request":
                        full = self._build_full_state()
                        await websocket.send(json.dumps({
                            "type": "reconcile_response",
                            "node_id": self.state.node_id,
                            "state": full,
                            "vector_clock": self.state.vector_clock.to_dict(),
                        }))

            except Exception:
                pass
            finally:
                if peer_id and peer_id in self._clients:
                    del self._clients[peer_id]

        async with websockets.serve(handler, "0.0.0.0", port):
            hb_interval = self.config.get("websocket", "heartbeat_interval",
                                          default=SYNC_HEARTBEAT_INTERVAL)
            reconcile_interval = self.config.get("websocket", "reconcile_interval",
                                                 default=SYNC_FULL_RECONCILE_INTERVAL)
            hb_counter = 0
            while self._running:
                await asyncio.sleep(hb_interval)
                hb_counter += hb_interval
                for pid, ws in list(self._clients.items()):
                    try:
                        await ws.send(json.dumps({
                            "type": "heartbeat",
                            "node_id": self.state.node_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }))
                    except Exception:
                        self._clients.pop(pid, None)

                if hb_counter >= reconcile_interval:
                    hb_counter = 0
                    await self._broadcast_reconcile()

    async def _broadcast_reconcile(self):
        full = self._build_full_state()
        msg = json.dumps({
            "type": "reconcile_push",
            "node_id": self.state.node_id,
            "state": full,
            "vector_clock": self.state.vector_clock.to_dict(),
        })
        for pid, ws in list(self._clients.items()):
            try:
                await ws.send(msg)
            except Exception:
                self._clients.pop(pid, None)

    def _handle_sync_push(self, data):
        remote_vc = VectorClock.from_dict(data.get("vector_clock", {}))
        changes = data.get("changes", [])
        for change in changes:
            key = change.get("key")
            content = change.get("content")
            remote_hash = change.get("hash")
            if key and content is not None:
                local_file = self.state.files.get(key, {})
                local_hash = local_file.get("hash")
                if local_hash != remote_hash:
                    if remote_vc.dominates(self.state.vector_clock) or \
                       local_hash is None:
                        self._apply_remote_change(key, content, change)
        self.state.vector_clock.merge(remote_vc)
        self.state.save()

    def _apply_remote_change(self, key, content, change):
        path = change.get("path")
        if not path:
            local_info = self.state.files.get(key, {})
            path = local_info.get("path")
        if not path:
            return
        try:
            filtered = self._strip_secrets(content)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                if isinstance(filtered, (dict, list)):
                    json.dump(filtered, f, indent=2)
                else:
                    f.write(str(filtered))
            self.state.record_file(key, path)
            if self.on_remote_update:
                self.on_remote_update(key, path)
        except Exception:
            pass

    def _strip_secrets(self, content):
        never_sync = self.config.get("never_sync_keys", default=[])
        if isinstance(content, dict):
            return {
                k: "***REDACTED***" if any(s in k.lower() for s in never_sync)
                else self._strip_secrets(v)
                for k, v in content.items()
            }
        elif isinstance(content, list):
            return [self._strip_secrets(item) for item in content]
        return content

    def _build_sync_response(self, request):
        requested_keys = request.get("keys", [])
        response_changes = []
        for key in requested_keys:
            info = self.state.files.get(key)
            if info and os.path.isfile(info["path"]):
                try:
                    with open(info["path"], "r") as f:
                        content = json.load(f)
                    content = self._strip_secrets(content)
                    response_changes.append({
                        "key": key,
                        "content": content,
                        "hash": info["hash"],
                        "path": info["path"],
                    })
                except Exception:
                    pass
        return {
            "type": "sync_response",
            "node_id": self.state.node_id,
            "changes": response_changes,
            "vector_clock": self.state.vector_clock.to_dict(),
        }

    def _build_full_state(self):
        state = {}
        for key, info in self.state.files.items():
            if os.path.isfile(info.get("path", "")):
                try:
                    with open(info["path"], "r") as f:
                        content = json.load(f)
                    state[key] = self._strip_secrets(content)
                except Exception:
                    pass
        return state

    async def push_changes(self, changes):
        msg = json.dumps({
            "type": "sync_push",
            "node_id": self.state.node_id,
            "changes": changes,
            "vector_clock": self.state.vector_clock.to_dict(),
        })
        for pid, ws in list(self._clients.items()):
            try:
                await ws.send(msg)
            except Exception:
                self._clients.pop(pid, None)

    def push_changes_sync(self, changes):
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(
                self.push_changes(changes), self._loop)

    def get_connected_peers(self):
        return list(self._clients.keys())

    async def connect_to_peer(self, host, port=None):
        try:
            import websockets
        except ImportError:
            return False
        port = port or self.config.get("websocket", "port", default=SYNC_PORT)
        try:
            ws = await websockets.connect(f"ws://{host}:{port}")
            await ws.send(json.dumps({
                "type": "hello",
                "node_id": self.state.node_id,
                "node_name": self.config.get("node_name", default="unknown"),
                "platform": sys.platform,
            }))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            if data.get("type") == "hello_ack":
                peer_id = data["node_id"]
                self._clients[peer_id] = ws
                self.state.peers[peer_id] = {
                    "name": data.get("node_name", peer_id),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "platform": data.get("platform", "unknown"),
                }
                self.state.save()
                return True
        except Exception:
            pass
        return False

    def connect_to_peer_sync(self, host, port=None):
        if self._loop and self._running:
            future = asyncio.run_coroutine_threadsafe(
                self.connect_to_peer(host, port), self._loop)
            try:
                return future.result(timeout=10)
            except Exception:
                return False
        return False


# ======================================================================
#  APPROACH 2: VPS RSYNC FALLBACK
# ======================================================================

class VPSSyncManager:
    def __init__(self, state, config):
        self.state = state
        self.config = config

    def _rsync_cmd(self):
        if IS_WINDOWS:
            for candidate in ["rsync", "cwrsync", "wsl rsync"]:
                try:
                    subprocess.run([candidate, "--version"],
                                   capture_output=True, timeout=5)
                    return candidate
                except Exception:
                    continue
            return None
        return "rsync"

    def _ssh_args(self):
        key = self.config.get("vps", "ssh_key", default="")
        if key and os.path.isfile(key):
            return ["-e", f"ssh -i {key} -o StrictHostKeyChecking=no"]
        return ["-e", "ssh -o StrictHostKeyChecking=no"]

    def push(self, local_paths=None):
        rsync = self._rsync_cmd()
        host = self.config.get("vps", "host", default="")
        user = self.config.get("vps", "user", default="")
        remote = self.config.get("vps", "remote_dir", default=SYNC_VPS_REMOTE_DIR)
        if not rsync or not host or not user:
            return False, "VPS sync not configured (host/user missing)"

        if local_paths is None:
            watcher = FileWatcher(self.state, self.config)
            local_paths = []
            for key, path in watcher._resolve_targets().items():
                if os.path.exists(path):
                    local_paths.append(path)

        results = []
        for path in local_paths:
            if not os.path.exists(path):
                continue
            try:
                dest = f"{user}@{host}:{remote}/{os.path.basename(path)}"
                cmd = [rsync, "-avz", "--delete"] + self._ssh_args() + [path, dest]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                results.append((path, result.returncode == 0, result.stderr.strip()))
            except Exception as e:
                results.append((path, False, str(e)))

        self.state.last_vps_sync = datetime.now(timezone.utc).isoformat()
        self.state.save()
        ok = all(r[1] for r in results)
        msg = "; ".join(f"{os.path.basename(r[0])}: {'OK' if r[1] else r[2]}" for r in results)
        return ok, msg

    def pull(self, local_paths=None):
        rsync = self._rsync_cmd()
        host = self.config.get("vps", "host", default="")
        user = self.config.get("vps", "user", default="")
        remote = self.config.get("vps", "remote_dir", default=SYNC_VPS_REMOTE_DIR)
        if not rsync or not host or not user:
            return False, "VPS sync not configured"

        if local_paths is None:
            watcher = FileWatcher(self.state, self.config)
            local_paths = []
            for key, path in watcher._resolve_targets().items():
                if os.path.isfile(path):
                    local_paths.append(path)
                elif os.path.isdir(path):
                    local_paths.append(path)

        results = []
        for path in local_paths:
            try:
                src = f"{user}@{host}:{remote}/{os.path.basename(path)}"
                os.makedirs(os.path.dirname(path) if os.path.isfile(path)
                            else path, exist_ok=True)
                trail = "/" if os.path.isdir(path) else ""
                cmd = [rsync, "-avz"] + self._ssh_args() + [src + trail, path + trail]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                results.append((path, result.returncode == 0, result.stderr.strip()))
            except Exception as e:
                results.append((path, False, str(e)))

        self.state.last_vps_sync = datetime.now(timezone.utc).isoformat()
        self.state.save()
        ok = all(r[1] for r in results)
        msg = "; ".join(f"{os.path.basename(r[0])}: {'OK' if r[1] else r[2]}" for r in results)
        return ok, msg

    def push_tar_ssh(self, local_paths=None):
        """Fallback for Windows without rsync: tar + SSH."""
        host = self.config.get("vps", "host", default="")
        user = self.config.get("vps", "user", default="")
        remote = self.config.get("vps", "remote_dir", default=SYNC_VPS_REMOTE_DIR)
        key = self.config.get("vps", "ssh_key", default="")
        if not host or not user:
            return False, "VPS not configured"

        if local_paths is None:
            watcher = FileWatcher(self.state, self.config)
            local_paths = [p for p in watcher._resolve_targets().values()
                           if os.path.exists(p)]

        import tempfile
        tar_path = os.path.join(tempfile.gettempdir(), "whim_sync.tar.gz")
        try:
            import tarfile
            with tarfile.open(tar_path, "w:gz") as tf:
                for path in local_paths:
                    if os.path.exists(path):
                        tf.add(path, arcname=os.path.basename(path))

            ssh_key_arg = ["-i", key] if key and os.path.isfile(key) else []
            cmd = (["scp", "-o", "StrictHostKeyChecking=no"] + ssh_key_arg +
                   [tar_path, f"{user}@{host}:{remote}/whim_sync.tar.gz"])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                extract_cmd = (
                    ["ssh", "-o", "StrictHostKeyChecking=no"] + ssh_key_arg +
                    [f"{user}@{host}",
                     f"cd {remote} && tar xzf whim_sync.tar.gz && rm whim_sync.tar.gz"])
                subprocess.run(extract_cmd, capture_output=True, text=True, timeout=60)
                self.state.last_vps_sync = datetime.now(timezone.utc).isoformat()
                self.state.save()
                return True, "Push via tar+SSH OK"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)
        finally:
            if os.path.isfile(tar_path):
                os.remove(tar_path)


# ======================================================================
#  APPROACH 3: CRDT LIVE COLLABORATION
# ======================================================================

class SimpleCRDT:
    """
    A simple last-writer-wins element set (LWW-Element-Set) CRDT.
    Each key maps to (value, timestamp, node_id). Merges by taking
    the latest timestamp per key. No external dependencies required.
    """

    def __init__(self, node_id):
        self.node_id = node_id
        self.elements = {}

    def set(self, key, value):
        ts = time.time()
        self.elements[key] = {
            "value": value,
            "timestamp": ts,
            "node_id": self.node_id,
        }

    def get(self, key, default=None):
        elem = self.elements.get(key)
        if elem:
            return elem["value"]
        return default

    def merge(self, other_elements):
        for key, remote in other_elements.items():
            local = self.elements.get(key)
            if local is None:
                self.elements[key] = remote
            elif remote["timestamp"] > local["timestamp"]:
                self.elements[key] = remote
            elif (remote["timestamp"] == local["timestamp"] and
                  remote["node_id"] > local["node_id"]):
                self.elements[key] = remote

    def to_dict(self):
        return dict(self.elements)

    @classmethod
    def from_dict(cls, node_id, data):
        crdt = cls(node_id)
        crdt.elements = dict(data)
        return crdt

    def snapshot(self):
        return {k: v["value"] for k, v in self.elements.items()}


class CRDTSyncManager:
    def __init__(self, state, config):
        self.state = state
        self.config = config
        self.documents = {}

    def get_or_create(self, doc_id):
        if doc_id not in self.documents:
            self.documents[doc_id] = SimpleCRDT(self.state.node_id)
        return self.documents[doc_id]

    def load_json_as_crdt(self, doc_id, filepath):
        crdt = self.get_or_create(doc_id)
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        crdt.set(k, v)
            except Exception:
                pass
        return crdt

    def merge_remote(self, doc_id, remote_elements):
        crdt = self.get_or_create(doc_id)
        crdt.merge(remote_elements)
        return crdt

    def save_crdt_to_file(self, doc_id, filepath):
        crdt = self.documents.get(doc_id)
        if not crdt:
            return
        snapshot = crdt.snapshot()
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(snapshot, f, indent=2)

    def get_all_elements(self, doc_id):
        crdt = self.documents.get(doc_id)
        if crdt:
            return crdt.to_dict()
        return {}


# ======================================================================
#  APPROACH 4: GIT-BASED SYNC
# ======================================================================

class GitSyncManager:
    def __init__(self, state, config):
        self.state = state
        self.config = config
        self._timer = None
        self._running = False

    def _git_dir(self):
        if IS_WINDOWS:
            base = os.environ.get("APPDATA", os.path.join(
                os.path.expanduser("~"), "AppData", "Roaming"))
            return os.path.join(base, "OpenClaw")
        return os.path.expanduser("~/.openclaw")

    def init_repo(self):
        git_dir = self._git_dir()
        os.makedirs(git_dir, exist_ok=True)
        gitdir = os.path.join(git_dir, ".git")
        if not os.path.isdir(gitdir):
            subprocess.run(["git", "init"], cwd=git_dir,
                           capture_output=True, timeout=30)
            gitignore = os.path.join(git_dir, ".gitignore")
            with open(gitignore, "w") as f:
                f.write("*.log\n*.pyc\n__pycache__/\nsandboxes/\n*.tmp\n")

        repo_url = self.config.get("git", "repo_url", default="")
        if repo_url:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=git_dir, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                subprocess.run(
                    ["git", "remote", "add", "origin", repo_url],
                    cwd=git_dir, capture_output=True, timeout=10)

    def commit_and_push(self):
        git_dir = self._git_dir()
        if not os.path.isdir(os.path.join(git_dir, ".git")):
            return False, "Not a git repo"
        try:
            subprocess.run(["git", "add", "-A"], cwd=git_dir,
                           capture_output=True, timeout=30)
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=git_dir, capture_output=True, timeout=10)
            if result.returncode == 0:
                return True, "No changes to commit"
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            subprocess.run(
                ["git", "commit", "-m",
                 f"Whim sync: {self.state.node_id} @ {ts}"],
                cwd=git_dir, capture_output=True, timeout=30,
                env={**os.environ,
                     "GIT_AUTHOR_NAME": "Whim Sync",
                     "GIT_AUTHOR_EMAIL": "whim@localhost",
                     "GIT_COMMITTER_NAME": "Whim Sync",
                     "GIT_COMMITTER_EMAIL": "whim@localhost"})

            repo_url = self.config.get("git", "repo_url", default="")
            branch = self.config.get("git", "branch", default="main")
            if repo_url:
                push_result = subprocess.run(
                    ["git", "push", "origin", branch],
                    cwd=git_dir, capture_output=True, text=True, timeout=60)
                if push_result.returncode != 0:
                    return False, push_result.stderr.strip()

            self.state.last_git_sync = datetime.now(timezone.utc).isoformat()
            self.state.save()
            return True, "Committed and pushed"
        except Exception as e:
            return False, str(e)

    def pull(self):
        git_dir = self._git_dir()
        if not os.path.isdir(os.path.join(git_dir, ".git")):
            return False, "Not a git repo"
        try:
            branch = self.config.get("git", "branch", default="main")
            result = subprocess.run(
                ["git", "pull", "origin", branch, "--rebase"],
                cwd=git_dir, capture_output=True, text=True, timeout=60,
                env={**os.environ,
                     "GIT_AUTHOR_NAME": "Whim Sync",
                     "GIT_AUTHOR_EMAIL": "whim@localhost",
                     "GIT_COMMITTER_NAME": "Whim Sync",
                     "GIT_COMMITTER_EMAIL": "whim@localhost"})
            self.state.last_git_sync = datetime.now(timezone.utc).isoformat()
            self.state.save()
            if result.returncode == 0:
                return True, "Pulled successfully"
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def start_auto_commit(self):
        if self._running:
            return
        self._running = True
        interval = self.config.get("git", "auto_commit_interval",
                                   default=SYNC_GIT_COMMIT_INTERVAL)
        def _loop():
            while self._running:
                time.sleep(interval)
                if self._running:
                    self.commit_and_push()
        self._timer = threading.Thread(target=_loop, daemon=True)
        self._timer.start()

    def stop_auto_commit(self):
        self._running = False


# ======================================================================
#  APPROACH 5: HYBRID (Tailscale WS + VPS Fallback)
# ======================================================================

class HybridSyncManager:
    def __init__(self, state, config, on_remote_update=None):
        self.state = state
        self.config = config
        self.ws_daemon = WebSocketSyncDaemon(state, config, on_remote_update)
        self.vps_sync = VPSSyncManager(state, config)
        self.watcher = FileWatcher(state, config, self._on_local_change)
        self._running = False
        self._vps_thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        ws_enabled = self.config.get("websocket", "enabled", default=True)
        vps_enabled = self.config.get("vps", "enabled", default=True)
        if ws_enabled:
            self.ws_daemon.start()
        if vps_enabled:
            if self.config.get("vps", "auto_pull_on_open", default=True):
                threading.Thread(target=self._vps_pull_bg, daemon=True).start()
        self.watcher.start()

    def stop(self):
        self._running = False
        self.watcher.stop()
        self.ws_daemon.stop()
        if self.config.get("vps", "auto_push_on_close", default=True):
            self._vps_push_bg()

    def _on_local_change(self, key, path, action):
        peers = self.ws_daemon.get_connected_peers()
        if peers:
            try:
                with open(path, "r") as f:
                    content = json.load(f)
                changes = [{
                    "key": key,
                    "content": content,
                    "hash": self.state.file_hash(path),
                    "path": path,
                }]
                self.ws_daemon.push_changes_sync(changes)
                self.state.last_ws_sync = datetime.now(timezone.utc).isoformat()
            except Exception:
                pass
        else:
            self.state.queue_change(key, path)
            self.state.save()

    def _vps_pull_bg(self):
        try:
            self.vps_sync.pull()
        except Exception:
            pass

    def _vps_push_bg(self):
        try:
            self.vps_sync.push()
        except Exception:
            pass

    def manual_push_vps(self):
        return self.vps_sync.push()

    def manual_pull_vps(self):
        return self.vps_sync.pull()

    def connect_peer(self, host, port=None):
        return self.ws_daemon.connect_to_peer_sync(host, port)

    def get_status(self):
        peers = self.ws_daemon.get_connected_peers()
        return {
            "mode": self.config.get("mode", default="hybrid"),
            "running": self._running,
            "ws_peers": len(peers),
            "ws_peer_ids": peers,
            "last_ws_sync": self.state.last_ws_sync,
            "last_vps_sync": self.state.last_vps_sync,
            "last_git_sync": self.state.last_git_sync,
            "queue_size": len(self.state.local_queue),
            "tracked_files": len(self.state.files),
            "node_id": self.state.node_id,
        }


# ======================================================================
#  APPROACH 6: MULTI-TERMINAL SESSION SHARING (MIRROR)
# ======================================================================

class SessionMirrorServer:
    def __init__(self, state, config):
        self.state = state
        self.config = config
        self._running = False
        self._loop = None
        self._thread = None
        self._viewers = {}
        self._current_session = {}
        self._control_holder = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception:
            pass

    async def _serve(self):
        try:
            import websockets
        except ImportError:
            return

        port = self.config.get("mirror", "port", default=MIRROR_PORT)

        async def handler(websocket, path=None):
            viewer_id = str(uuid.uuid4())[:8]
            self._viewers[viewer_id] = websocket
            try:
                await websocket.send(json.dumps({
                    "type": "mirror_init",
                    "session": self._current_session,
                    "host_node": self.state.node_id,
                }))
                async for message in websocket:
                    data = json.loads(message)
                    if data.get("type") == "control_request":
                        allow = self.config.get("mirror", "allow_control", default=False)
                        if allow and self._control_holder is None:
                            self._control_holder = viewer_id
                            await websocket.send(json.dumps({
                                "type": "control_granted"}))
                        else:
                            await websocket.send(json.dumps({
                                "type": "control_denied"}))
                    elif data.get("type") == "control_input":
                        if viewer_id == self._control_holder:
                            pass
                    elif data.get("type") == "release_control":
                        if viewer_id == self._control_holder:
                            self._control_holder = None
            except Exception:
                pass
            finally:
                self._viewers.pop(viewer_id, None)
                if self._control_holder == viewer_id:
                    self._control_holder = None

        async with websockets.serve(handler, "0.0.0.0", port):
            while self._running:
                await asyncio.sleep(1)

    def broadcast_session_update(self, session_data):
        self._current_session = session_data
        if not self._loop or not self._viewers:
            return
        msg = json.dumps({
            "type": "mirror_update",
            "session": session_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        async def _send():
            for vid, ws in list(self._viewers.items()):
                try:
                    await ws.send(msg)
                except Exception:
                    self._viewers.pop(vid, None)
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(), self._loop)

    def get_viewer_count(self):
        return len(self._viewers)

    def get_control_holder(self):
        return self._control_holder


class SessionMirrorClient:
    def __init__(self, on_session_update=None):
        self.on_session_update = on_session_update
        self._ws = None
        self._running = False
        self._thread = None
        self._has_control = False

    def connect(self, host, port=None):
        port = port or MIRROR_PORT
        self._running = True
        self._thread = threading.Thread(
            target=self._run_client, args=(host, port), daemon=True)
        self._thread.start()

    def disconnect(self):
        self._running = False

    def _run_client(self, host, port):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._client_loop(host, port))
        except Exception:
            pass

    async def _client_loop(self, host, port):
        try:
            import websockets
        except ImportError:
            return
        try:
            async with websockets.connect(f"ws://{host}:{port}") as ws:
                self._ws = ws
                async for message in ws:
                    if not self._running:
                        break
                    data = json.loads(message)
                    if data.get("type") in ("mirror_init", "mirror_update"):
                        if self.on_session_update:
                            self.on_session_update(data.get("session", {}))
                    elif data.get("type") == "control_granted":
                        self._has_control = True
                    elif data.get("type") == "control_denied":
                        self._has_control = False
        except Exception:
            pass

    async def request_control(self):
        if self._ws:
            await self._ws.send(json.dumps({"type": "control_request"}))

    async def release_control(self):
        if self._ws:
            self._has_control = False
            await self._ws.send(json.dumps({"type": "release_control"}))


# ======================================================================
#  APPROACH 7: PHONE AS SYNC BRIDGE
# ======================================================================

class PhoneBridgeRelay:
    """
    Uses the existing Whim.m HTTP server (port 8089) to relay sync data
    through connected phones acting as store-and-forward bridges.
    """

    def __init__(self, state, config):
        self.state = state
        self.config = config

    def push_to_phone(self, host, port=None):
        port = port or self.config.get("phone_bridge", "relay_port", default=8089)
        changes = self.state.drain_queue()
        if not changes:
            return True, "Nothing to push"
        payload = {
            "type": "whim_sync_relay",
            "source_node": self.state.node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changes": changes,
            "vector_clock": self.state.vector_clock.to_dict(),
        }
        try:
            import urllib.request
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"http://{host}:{port}/sync_relay",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, "Pushed to phone bridge"
            return False, f"HTTP {resp.status}"
        except Exception as e:
            return False, str(e)

    def pull_from_phone(self, host, port=None):
        port = port or self.config.get("phone_bridge", "relay_port", default=8089)
        try:
            import urllib.request
            req = urllib.request.Request(
                f"http://{host}:{port}/sync_relay?node={self.state.node_id}",
                method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    changes = data.get("changes", [])
                    if changes:
                        remote_vc = VectorClock.from_dict(
                            data.get("vector_clock", {}))
                        self.state.vector_clock.merge(remote_vc)
                        self.state.save()
                    return True, f"Pulled {len(changes)} changes from phone bridge"
            return False, "No data"
        except Exception as e:
            return False, str(e)

    def discover_phones(self):
        """Try known Tailscale IPs from device_locations.json."""
        phones = []
        if IS_WINDOWS:
            dl_path = os.path.join(os.path.expanduser("~"), "Documents",
                                   "Whim", "config", "device_locations.json")
        else:
            dl_path = os.path.expanduser(
                "~/vaults/WHIM/config/device_locations.json")
        if os.path.isfile(dl_path):
            try:
                with open(dl_path, "r") as f:
                    data = json.load(f)
                for dev in data.get("devices", []):
                    ts_ip = dev.get("tailscale_ip")
                    if ts_ip and "PC" not in dev.get("name", ""):
                        phones.append({
                            "name": dev["name"],
                            "ip": ts_ip,
                        })
            except Exception:
                pass
        return phones


# ======================================================================
#  UNIFIED SYNC ENGINE — orchestrates all approaches
# ======================================================================

class WhimSyncEngine:
    def __init__(self, on_remote_update=None, on_status_change=None):
        self.state = SyncState()
        self.config = SyncConfig()
        self.on_remote_update = on_remote_update
        self.on_status_change = on_status_change

        self.hybrid = HybridSyncManager(
            self.state, self.config, on_remote_update)
        self.crdt = CRDTSyncManager(self.state, self.config)
        self.git = GitSyncManager(self.state, self.config)
        self.mirror_server = SessionMirrorServer(self.state, self.config)
        self.mirror_client = SessionMirrorClient()
        self.phone_bridge = PhoneBridgeRelay(self.state, self.config)

        self._running = False

    def start(self):
        if not self.config.get("enabled", default=False):
            return
        self._running = True
        mode = self.config.get("mode", default="hybrid")

        self.hybrid.start()

        if self.config.get("git", "enabled", default=False):
            self.git.init_repo()
            self.git.pull()
            self.git.start_auto_commit()

        if self.config.get("mirror", "enabled", default=True):
            self.mirror_server.start()

        if self.on_status_change:
            self.on_status_change(self.get_status())

    def stop(self):
        self._running = False
        self.hybrid.stop()
        self.git.stop_auto_commit()
        self.mirror_server.stop()
        self.mirror_client.disconnect()
        self.state.save()
        self.config.save()

    def get_status(self):
        status = self.hybrid.get_status()
        status["git_enabled"] = self.config.get("git", "enabled", default=False)
        status["mirror_viewers"] = self.mirror_server.get_viewer_count()
        status["mirror_control"] = self.mirror_server.get_control_holder()
        status["crdt_docs"] = len(self.crdt.documents)
        return status

    def connect_peer(self, host, port=None):
        return self.hybrid.connect_peer(host, port)

    def push_vps(self):
        return self.hybrid.manual_push_vps()

    def pull_vps(self):
        return self.hybrid.manual_pull_vps()

    def push_git(self):
        return self.git.commit_and_push()

    def pull_git(self):
        return self.git.pull()

    def push_phone(self, host, port=None):
        return self.phone_bridge.push_to_phone(host, port)

    def pull_phone(self, host, port=None):
        return self.phone_bridge.pull_from_phone(host, port)

    def discover_phones(self):
        return self.phone_bridge.discover_phones()

    def broadcast_session(self, session_data):
        self.mirror_server.broadcast_session_update(session_data)

    def watch_mirror(self, host, port=None, callback=None):
        self.mirror_client.on_session_update = callback
        self.mirror_client.connect(host, port)

    def update_config(self, updates):
        self.config._deep_merge(self.config.data, updates)
        self.config.save()

    def get_sync_paths(self):
        watcher = FileWatcher(self.state, self.config)
        return watcher.get_sync_paths()
