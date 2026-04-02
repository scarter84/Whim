import asyncio
import json
import threading
import queue
import uuid
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import requests
import websockets

# ---- CONFIG ----
DEFAULT_WS_URL = "ws://127.0.0.1:18789"  # gateway ws url (same port as Control UI)
DEFAULT_TOKEN = ""                       # paste gateway token here or in UI

# If your XTTS is running as a local server, put its endpoint here.
# Examples (you will adjust to your actual XTTS server):
#   http://127.0.0.1:8020/tts
#   http://127.0.0.1:5002/api/tts
DEFAULT_XTTS_URL = "http://127.0.0.1:8020/tts"

# ---- THREAD SAFE QUEUES ----
incoming = queue.Queue()
outgoing = queue.Queue()

# ---- UTIL ----
def jdump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)

def new_id(prefix="req"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"

# ---- WS CLIENT (runs in background thread) ----
class GatewayClient:
    def __init__(self):
        self.ws = None
        self.connected = False
        self.device_token = None

    async def connect(self, ws_url, token, scopes):
        self.connected = False
        self.device_token = None

        async with websockets.connect(ws_url) as ws:
            self.ws = ws

            # 1) wait for challenge
            challenge = json.loads(await ws.recv())
            incoming.put(("event", challenge))

            if not (challenge.get("type") == "event" and challenge.get("event") == "connect.challenge"):
                incoming.put(("log", "Expected connect.challenge, got something else."))
                return

            nonce = challenge["payload"]["nonce"]
            ts = challenge["payload"]["ts"]

            # 2) send connect (first client frame must be connect request)
            req_id = new_id("connect")
            connect_req = {
                "type": "req",
                "id": req_id,
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id": "tkui",
                        "version": "0.1.0",
                        "platform": "linux",
                        "mode": "operator",
                    },
                    "role": "operator",
                    "scopes": scopes,
                    "caps": [],
                    "commands": [],
                    "permissions": {},
                    "auth": {"token": token} if token else {},
                    "locale": "en-US",
                    "userAgent": "openclaw-tkui/0.1.0",
                    # For local loopback you typically can keep identity simple.
                    # For remote + secure pairing, you'll want a real keypair + signature.
                    "device": {
                        "id": "tkui-local",
                        "publicKey": "",
                        "signature": "",
                        "signedAt": ts,
                        "nonce": nonce,
                    },
                },
            }
            await ws.send(json.dumps(connect_req))

            # 3) main loop: pump incoming frames + send outgoing requests
            self.connected = True
            incoming.put(("log", "WS connected; waiting for hello-ok..."))

            while True:
                # outbound
                try:
                    while True:
                        msg = outgoing.get_nowait()
                        await ws.send(json.dumps(msg))
                except queue.Empty:
                    pass

                # inbound (with timeout so we can continue pumping outbound)
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.1)
                    packet = json.loads(raw)
                    incoming.put(("ws", packet))

                    # Grab deviceToken if Gateway issues one in hello-ok
                    if packet.get("type") == "res" and packet.get("ok") and isinstance(packet.get("payload"), dict):
                        payload = packet["payload"]
                        auth = payload.get("auth")
                        if isinstance(auth, dict) and auth.get("deviceToken"):
                            self.device_token = auth["deviceToken"]
                            incoming.put(("log", "Received deviceToken (you can persist this for later)."))

                except asyncio.TimeoutError:
                    pass

async def ws_runner(ws_url, token, scopes):
    client = GatewayClient()
    try:
        await client.connect(ws_url, token, scopes)
    except Exception as e:
        incoming.put(("log", f"WS error: {e!r}"))

def start_ws_thread(ws_url, token, scopes):
    t = threading.Thread(target=lambda: asyncio.run(ws_runner(ws_url, token, scopes)), daemon=True)
    t.start()
    return t

# ---- TKINTER UI ----
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OpenClaw Tk Control UI (starter)")
        self.geometry("1100x750")

        self.ws_thread = None

        # top connection bar
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Gateway WS URL:").pack(side="left")
        self.ws_url_var = tk.StringVar(value=DEFAULT_WS_URL)
        ttk.Entry(top, textvariable=self.ws_url_var, width=32).pack(side="left", padx=6)

        ttk.Label(top, text="Token:").pack(side="left")
        self.token_var = tk.StringVar(value=DEFAULT_TOKEN)
        ttk.Entry(top, textvariable=self.token_var, width=36, show="•").pack(side="left", padx=6)

        self.approvals_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Include approvals scope", variable=self.approvals_var).pack(side="left", padx=8)

        ttk.Button(top, text="Connect", command=self.on_connect).pack(side="left", padx=8)

        # notebook (tabs)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.chat_tab = ttk.Frame(self.nb)
        self.sessions_tab = ttk.Frame(self.nb)
        self.presence_tab = ttk.Frame(self.nb)
        self.xtts_tab = ttk.Frame(self.nb)
        self.events_tab = ttk.Frame(self.nb)

        self.nb.add(self.chat_tab, text="Chat")
        self.nb.add(self.sessions_tab, text="Sessions")
        self.nb.add(self.presence_tab, text="Presence")
        self.nb.add(self.xtts_tab, text="XTTS Voice Clone")
        self.nb.add(self.events_tab, text="Events/Debug")

        self.build_chat()
        self.build_sessions()
        self.build_presence()
        self.build_xtts()
        self.build_events()

        # pump incoming queue
        self.after(50, self.pump_incoming)

    def log_events(self, line):
        self.events_box.insert("end", line + "\n")
        self.events_box.see("end")

    def on_connect(self):
        ws_url = self.ws_url_var.get().strip()
        token = self.token_var.get().strip()

        scopes = ["operator.read", "operator.write"]
        if self.approvals_var.get():
            scopes.append("operator.approvals")

        self.log_events(f"Connecting to {ws_url} ...")
        self.ws_thread = start_ws_thread(ws_url, token, scopes)

    # ---------- Chat tab ----------
    def build_chat(self):
        frm = self.chat_tab

        self.chat_log = ScrolledText(frm, height=28)
        self.chat_log.pack(fill="both", expand=True, padx=8, pady=8)

        bottom = ttk.Frame(frm)
        bottom.pack(fill="x", padx=8, pady=(0,8))

        self.chat_entry = ttk.Entry(bottom)
        self.chat_entry.pack(side="left", fill="x", expand=True)

        ttk.Button(bottom, text="Send", command=self.chat_send).pack(side="left", padx=6)
        ttk.Button(bottom, text="Stop (abort)", command=self.chat_abort).pack(side="left")

    def chat_send(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, "end")

        # NOTE: We don't know your exact sessionKey yet.
        # Once we wire sessions.list and selection, we'll send to the chosen session.
        # For now, send without sessionKey only if your gateway supports it; otherwise it will error.
        req = {
            "type": "req",
            "id": new_id("chatSend"),
            "method": "chat.send",
            "params": {
                "text": text,
                # "sessionKey": "<fill once you pick a session>",
                "idempotencyKey": uuid.uuid4().hex,
            },
        }
        outgoing.put(req)
        self.chat_log.insert("end", f"> {text}\n")
        self.chat_log.see("end")

    def chat_abort(self):
        req = {
            "type": "req",
            "id": new_id("chatAbort"),
            "method": "chat.abort",
            "params": {
                # "sessionKey": "<fill once you pick a session>",
            },
        }
        outgoing.put(req)
        self.chat_log.insert("end", "[abort requested]\n")
        self.chat_log.see("end")

    # ---------- Sessions tab ----------
    def build_sessions(self):
        frm = self.sessions_tab
        ttk.Button(frm, text="Refresh sessions.list", command=self.sessions_list).pack(anchor="w", padx=8, pady=8)
        self.sessions_box = ScrolledText(frm, height=32)
        self.sessions_box.pack(fill="both", expand=True, padx=8, pady=8)

    def sessions_list(self):
        req = {"type": "req", "id": new_id("sessionsList"), "method": "sessions.list", "params": {}}
        outgoing.put(req)

    # ---------- Presence tab ----------
    def build_presence(self):
        frm = self.presence_tab
        ttk.Button(frm, text="Refresh system-presence", command=self.presence_list).pack(anchor="w", padx=8, pady=8)
        self.presence_box = ScrolledText(frm, height=32)
        self.presence_box.pack(fill="both", expand=True, padx=8, pady=8)

    def presence_list(self):
        req = {"type": "req", "id": new_id("presence"), "method": "system-presence", "params": {}}
        outgoing.put(req)

    # ---------- XTTS tab ----------
    def build_xtts(self):
        frm = self.xtts_tab

        row1 = ttk.Frame(frm)
        row1.pack(fill="x", padx=8, pady=8)
        ttk.Label(row1, text="XTTS URL:").pack(side="left")
        self.xtts_url_var = tk.StringVar(value=DEFAULT_XTTS_URL)
        ttk.Entry(row1, textvariable=self.xtts_url_var, width=60).pack(side="left", padx=6)

        row2 = ttk.Frame(frm)
        row2.pack(fill="x", padx=8, pady=(0,8))
        ttk.Label(row2, text="Text:").pack(side="left")
        self.xtts_text_var = tk.StringVar(value="Hello from XTTS.")
        ttk.Entry(row2, textvariable=self.xtts_text_var).pack(side="left", fill="x", expand=True, padx=6)

        row3 = ttk.Frame(frm)
        row3.pack(fill="x", padx=8, pady=(0,8))
        ttk.Label(row3, text="Voice profile path (or speaker id):").pack(side="left")
        self.xtts_voice_var = tk.StringVar(value="")
        ttk.Entry(row3, textvariable=self.xtts_voice_var).pack(side="left", fill="x", expand=True, padx=6)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(btns, text="Test XTTS (HTTP)", command=self.xtts_test).pack(side="left")
        ttk.Button(btns, text="(Later) Apply voice to OpenClaw config", command=self.xtts_apply_to_openclaw_stub).pack(side="left", padx=8)

        self.xtts_out = ScrolledText(frm, height=26)
        self.xtts_out.pack(fill="both", expand=True, padx=8, pady=8)

    def xtts_test(self):
        url = self.xtts_url_var.get().strip()
        text = self.xtts_text_var.get().strip()
        voice = self.xtts_voice_var.get().strip()

        # This is intentionally generic because XTTS servers vary.
        # You will adapt payload keys to match your local XTTS server.
        payload = {
            "text": text,
            "voice": voice,
        }

        self.xtts_out.insert("end", f"POST {url}\n{jdump(payload)}\n")
        self.xtts_out.see("end")

        try:
            r = requests.post(url, json=payload, timeout=60)
            self.xtts_out.insert("end", f"Status: {r.status_code}\n")
            ct = r.headers.get("content-type", "")
            self.xtts_out.insert("end", f"Content-Type: {ct}\n")

            # If the server returns JSON:
            if "application/json" in ct:
                self.xtts_out.insert("end", jdump(r.json()) + "\n")
            else:
                # If it returns audio bytes, you'll want to save to a file and play it.
                self.xtts_out.insert("end", f"Received {len(r.content)} bytes\n")
                # Example save:
                with open("xtts_test_output.bin", "wb") as f:
                    f.write(r.content)
                self.xtts_out.insert("end", "Saved response to xtts_test_output.bin (rename to .wav if it is WAV)\n")

        except Exception as e:
            self.xtts_out.insert("end", f"XTTS error: {e!r}\n")

        self.xtts_out.see("end")

    def xtts_apply_to_openclaw_stub(self):
        # We will implement this once we know where OpenClaw expects voice/TTS config.
        # Likely via config.get/config.schema/config.set/config.apply,
        # but we need the exact schema keys from your gateway.
        self.xtts_out.insert("end", "Not wired yet. Next step: fetch config.schema + config.get and locate TTS/voice fields.\n")
        self.xtts_out.see("end")

    # ---------- Events tab ----------
    def build_events(self):
        self.events_box = ScrolledText(self.events_tab, height=40)
        self.events_box.pack(fill="both", expand=True, padx=8, pady=8)

    def pump_incoming(self):
        try:
            while True:
                kind, payload = incoming.get_nowait()

                if kind in ("event", "ws"):
                    self.log_events(jdump(payload))

                    # crude routing to tabs
                    if isinstance(payload, dict):
                        if payload.get("method") == "chat" or payload.get("event", "").startswith("chat"):
                            self.chat_log.insert("end", jdump(payload) + "\n")
                            self.chat_log.see("end")

                        # show responses to sessions.list
                        if payload.get("type") == "res" and payload.get("id", "").startswith("sessionsList"):
                            self.sessions_box.delete("1.0", "end")
                            self.sessions_box.insert("end", jdump(payload) + "\n")

                        # show responses to system-presence
                        if payload.get("type") == "res" and payload.get("id", "").startswith("presence"):
                            self.presence_box.delete("1.0", "end")
                            self.presence_box.insert("end", jdump(payload) + "\n")

                elif kind == "log":
                    self.log_events(str(payload))

        except queue.Empty:
            pass

        self.after(50, self.pump_incoming)

if __name__ == "__main__":
    App().mainloop()