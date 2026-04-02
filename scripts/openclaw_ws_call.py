import asyncio, json, os, sys, uuid
import websockets

WS_URL = os.environ.get("OPENCLAW_WS_URL", "ws://127.0.0.1:18789")
TOKEN  = os.environ.get("OPENCLAW_TOKEN", "")
METHOD = sys.argv[1] if len(sys.argv) > 1 else None
PARAMS = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

if not METHOD:
    print("Usage: python3 openclaw_ws_call.py <method> [json_params]")
    sys.exit(2)

def rid(prefix="req"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"

async def main():
    async with websockets.connect(WS_URL) as ws:
        msg = json.loads(await ws.recv())
        if not (msg.get("type") == "event" and msg.get("event") == "connect.challenge"):
            print(json.dumps({"error":"expected connect.challenge","got":msg}, indent=2))
            return

        nonce = msg["payload"]["nonce"]
        ts = msg["payload"]["ts"]

        connect_id = rid("connect")
        connect_req = {
            "type": "req",
            "id": connect_id,
            "method": "connect",
            "params": {
                "minProtocol": 3,
                "maxProtocol": 3,
                "client": {"id":"terminal","version":"0.1.0","platform":"linux","mode":"operator"},
                "role": "operator",
                "scopes": ["operator.read","operator.write","operator.approvals"],
                "caps": [],
                "commands": [],
                "permissions": {},
                "auth": {"token": TOKEN} if TOKEN else {},
                "locale": "en-US",
                "userAgent": "openclaw-terminal/0.1.0",
                "device": {"id":"terminal-local","publicKey":"","signature":"","signedAt": ts,"nonce": nonce}
            }
        }
        await ws.send(json.dumps(connect_req))

        while True:
            res = json.loads(await ws.recv())
            if res.get("type") == "res" and res.get("id") == connect_id:
                if not res.get("ok"):
                    print(json.dumps(res, indent=2))
                    return
                break

        call_id = rid(METHOD.replace(".","_"))
        call_req = {"type":"req","id":call_id,"method":METHOD,"params":PARAMS}
        await ws.send(json.dumps(call_req))

        while True:
            res = json.loads(await ws.recv())
            if res.get("type") == "res" and res.get("id") == call_id:
                print(json.dumps(res, indent=2))
                return

asyncio.run(main())
