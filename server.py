"""jev drone cam: a drone that finds a photo in a room by asking jev.

Serves public/ and one endpoint, POST /api/box, which sends a drone-cam frame
and a destination photo to jev on TypeSafe's API. The key stays server-side.

Run: TYPESAFE_API_KEY=... python3 server.py   (listens on 127.0.0.1:9470)
Env: TYPESAFE_API_KEY (required), DRONECAM_HOST, DRONECAM_PORT, DRONECAM_MODEL
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import signal
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("DRONECAM_HOST", "127.0.0.1")
PORT = int(os.environ.get("DRONECAM_PORT", "9470"))
API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = os.environ.get("DRONECAM_MODEL", "jev-1.14.0")
MAX_IMAGE_BYTES = 1_500_000
RATE_PER_MINUTE = 90  # bounds spend: about $0.0001 per call


KEY = os.environ.get("TYPESAFE_API_KEY") or ""
if not KEY:
    raise SystemExit("Set TYPESAFE_API_KEY to your TypeSafe API key.")
_calls: list[float] = []
_lock = threading.Lock()


def _rate_ok() -> bool:
    now = time.time()
    with _lock:
        _calls[:] = [t for t in _calls if now - t < 60]
        if len(_calls) >= RATE_PER_MINUTE:
            return False
        _calls.append(now)
        return True


def _jpeg_b64(data_url: str) -> str:
    """'data:image/jpeg;base64,...' or bare base64 -> validated base64."""
    b64 = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    raw = base64.b64decode(b64, validate=True)
    if len(raw) > MAX_IMAGE_BYTES or raw[:2] != b"\xff\xd8":
        raise ValueError("expected a JPEG under 1.5 MB")
    return b64


def ask_box(cam_b64: str, dest_b64: str) -> dict:
    cam, dst = f"img-{uuid.uuid4()}", f"img-{uuid.uuid4()}"
    body = {
        "model": MODEL,
        "state": {"drone cam": cam, "destination": dst},
        "assets": {
            cam: {"type": "image", "format": "jpg", "data_base64": cam_b64},
            dst: {"type": "image", "format": "jpg", "data_base64": dest_b64},
        },
        "questions": {
            "where": {"type": "box",
                      "instructions": "Where is the object shown in `destination` in `drone cam`?"},
            # A Box always returns a box, and its confidence could not tell the
            # rubber plant from the rattan basket (0.35 vs 0.46). This yes/no
            # question in the same call does (0.93 vs 0.03), so it is the gate.
            "seen": {"type": "noul",
                     "instructions": "Is the specific object shown in `destination` visible in `drone cam`?"},
        },
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "TypeSafe-Danger-Zone-Images": "true", "User-Agent": "jev-dronecam"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    ms = int((time.monotonic() - t0) * 1000)
    a = payload["answers"]["where"]
    b = a["box"]
    return {"box": [b["left"], b["top"], b["right"], b["bottom"]],
            "confidence": a.get("confidence"), "seen": payload["answers"]["seen"]["noul"], "ms": ms, "model": payload.get("model", MODEL)}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "public"), **kw)

    def log_message(self, fmt, *args):  # quiet static logs, keep API lines
        if self.path.startswith("/api/"):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _json(self, code: int, obj: dict) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/api/box":
            return self._json(404, {"error": "not found"})
        if not _rate_ok():
            return self._json(429, {"error": "slow down"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n > 2 * MAX_IMAGE_BYTES * 1.4:
                raise ValueError("request too large")
            req = json.loads(self.rfile.read(n))
            result = ask_box(_jpeg_b64(req["cam"]), _jpeg_b64(req["destination"]))
        except (KeyError, ValueError, binascii.Error) as exc:
            return self._json(400, {"error": str(exc)[:200]})
        except urllib.error.HTTPError as exc:
            return self._json(502, {"error": f"jev HTTP {exc.code}: {exc.read()[:200].decode('utf-8', 'replace')}"})
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return self._json(504, {"error": f"jev unreachable: {type(exc).__name__}"})
        self._json(200, result)


if __name__ == "__main__":
    print(f"jev drone cam on http://{HOST}:{PORT}  (model {MODEL})", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    # exit 0 on SIGTERM so a service manager records a clean stop, not a crash
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    server.serve_forever()
