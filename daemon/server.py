from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from .config import HOST, PORT

EventHandler = Callable[[dict], None]
StatsProvider = Callable[[], dict]


class _Handler(BaseHTTPRequestHandler):
    dispatch: EventHandler = staticmethod(lambda evt: None)
    stats: StatsProvider = staticmethod(lambda: {})

    def log_message(self, format: str, *args) -> None:
        return

    def do_POST(self) -> None:
        if self.path != "/event":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        try:
            type(self).dispatch(payload)
        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        if self.path == "/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                body = json.dumps(type(self).stats(), default=str).encode("utf-8")
            except Exception as exc:
                body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


class EventServer:
    def __init__(
        self,
        dispatch: EventHandler,
        stats: StatsProvider | None = None,
        *,
        host: str = HOST,
        port: int = PORT,
    ) -> None:
        handler_cls = type(
            "_BoundHandler",
            (_Handler,),
            {
                "dispatch": staticmethod(dispatch),
                "stats": staticmethod(stats or (lambda: {})),
            },
        )
        self._http = ThreadingHTTPServer((host, port), handler_cls)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._http.shutdown()
        self._http.server_close()
