"""Live dashboard server — Functionality #5. Pure stdlib (no FastAPI).

GET  /            the dashboard (single self-contained HTML file)
GET  /events      Server-Sent Events stream of the EventBus (with replay)
GET  /api/state   current run status + ledger snapshot
GET  /api/issues  demo issues (id + default mode)
POST /api/run     {"issue": "ISSUE-1", "mode": "auto"} → start a run
"""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..bus import BUS
from ..config import TEMPLATE_DIR, settings as load_settings
from ..util import color

STATIC = Path(__file__).parent / "static"


class RunManager:
    def __init__(self, backend: str | None) -> None:
        self.backend = backend
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.orch = None
        self.last_summary: dict | None = None
        self.last_error: str = ""

    @property
    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, issue: str, mode: str) -> bool:
        with self.lock:
            if self.running:
                return False
            self.last_error = ""

            def target():
                from ..pipeline import Orchestrator
                try:
                    self.orch = Orchestrator(backend_name=self.backend)
                    self.last_summary = self.orch.run_issue(issue, mode)
                except Exception as exc:
                    self.last_error = f"{type(exc).__name__}: {exc}"

            self.thread = threading.Thread(target=target, daemon=True)
            self.thread.start()
            return True


MANAGER: RunManager | None = None


def list_issues() -> list[dict]:
    from ..pipeline.orchestrator import parse_frontmatter
    issues = []
    for path in sorted((TEMPLATE_DIR / "issues").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        front = parse_frontmatter(text)
        title = next((l.lstrip("# ").strip() for l in text.splitlines()
                      if l.startswith("# ")), path.stem)
        issues.append({"id": path.stem, "mode": front.get("mode", "standard"),
                       "title": title})
    return issues


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet
        pass

    # ------------------------------------------------------------- util

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    # ------------------------------------------------------------ routes

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
        elif self.path == "/events":
            self._sse()
        elif self.path == "/api/state":
            snapshot = MANAGER.orch.ledger.snapshot() if (
                MANAGER and MANAGER.orch and MANAGER.orch.ledger) else None
            self._json({"running": bool(MANAGER and MANAGER.running),
                        "backend_pref": (MANAGER.backend if MANAGER else None)
                        or load_settings().backend_pref,
                        "has_key": load_settings().has_key,
                        "last_error": MANAGER.last_error if MANAGER else "",
                        "last_summary": MANAGER.last_summary if MANAGER else None,
                        "ledger": snapshot})
        elif self.path == "/api/issues":
            self._json(list_issues())
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/run":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "bad json"}, 400)
            return
        issue = payload.get("issue", "ISSUE-1")
        mode = payload.get("mode", "auto")
        if MANAGER.start(issue, mode):
            self._json({"started": True, "issue": issue, "mode": mode})
        else:
            self._json({"error": "a run is already in progress"}, 409)

    # --------------------------------------------------------------- SSE

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = BUS.subscribe(replay=True)
        try:
            self.wfile.write(b"retry: 1500\n\n")
            self.wfile.flush()
            while True:
                try:
                    event = q.get(timeout=15)
                    data = json.dumps(event).encode("utf-8")
                    self.wfile.write(b"data: " + data + b"\n\n")
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            BUS.unsubscribe(q)


def serve(port: int = 8765, backend: str | None = None) -> None:
    global MANAGER
    MANAGER = RunManager(backend)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(color(f"AgentGrid dashboard → http://127.0.0.1:{port}", "bold"))
    print("Start runs from the browser, or POST /api/run. Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()
