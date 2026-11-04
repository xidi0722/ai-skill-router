"""Minimal localhost-only HTTP API using the Python standard library."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .profile import load_schema
from .service import RouterService


MAX_BODY_BYTES = 1_000_000


def make_handler(
    profile_directory: str | Path,
    approval_ledger_path: str | Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    service = RouterService(profile_directory, approval_ledger_path=approval_ledger_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "UniversalModelRouter/0.1"

        def _send(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send(200, {"status": "ok", "bind_scope": "localhost"})
            elif self.path == "/profiles":
                self._send(200, service.profiles())
            elif self.path == "/schema":
                self._send(200, load_schema())
            else:
                self._send(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/route":
                self._send(404, {"error": "not_found"})
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > MAX_BODY_BYTES:
                    self._send(413, {"error": "request_body_size_invalid"})
                    return
                body = json.loads(self.rfile.read(content_length))
                if not isinstance(body, dict):
                    self._send(400, {"error": "request_must_be_a_json_object"})
                    return
                self._send(200, service.handle(body))
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(400, {"error": {"code": "invalid_request", "message": str(exc)}})
            except RuntimeError as exc:
                self._send(502, {"error": {"code": "execution_failed", "message": str(exc)}})
            except Exception:
                self._send(500, {"error": {"code": "internal_error", "message": "Internal error"}})

        def log_message(self, format: str, *args: Any) -> None:
            # Keep request bodies and credentials out of default access logs.
            return

    return Handler


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    profile_directory: str | Path = "profiles",
    approval_ledger_path: str | Path | None = None,
) -> None:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("The MVP HTTP API may only bind to localhost")
    server = ThreadingHTTPServer((host, port), make_handler(profile_directory, approval_ledger_path))
    print(f"Universal Model Router listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
