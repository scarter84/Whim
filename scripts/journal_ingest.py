import os, time
from flask import Flask, request, abort, jsonify

JOURNAL_DIR = os.path.expanduser(os.environ.get("JOURNAL_DIR", "~/Journal"))
TOKEN = os.environ.get("JOURNAL_TOKEN", "")

app = Flask(__name__)
os.makedirs(JOURNAL_DIR, exist_ok=True)

@app.get("/health")
def health():
    return "ok\n"

@app.get("/config")
def config():
    return jsonify({
        "journal_dir": JOURNAL_DIR,
        "auth_header": "X-Auth-Token",
        "endpoints": ["/health", "/config", "/ingest"]
    })

@app.post("/ingest")
def ingest():
    if not TOKEN:
        abort(500, "Server missing JOURNAL_TOKEN")
    if request.headers.get("X-Auth-Token") != TOKEN:
        abort(401)

    if "file" not in request.files:
        abort(400, "missing multipart form field: file")

    f = request.files["file"]
    orig = os.path.basename(f.filename or "upload.bin")
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in orig).strip()
    out = os.path.join(JOURNAL_DIR, f"{ts}_{safe}")
    f.save(out)
    return out + "\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8787)
