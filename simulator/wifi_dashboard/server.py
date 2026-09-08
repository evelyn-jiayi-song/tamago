#!/usr/bin/env python3
"""Laptop proxy for the separate ESP32 Wi-Fi dashboard experiment."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


DASHBOARD_DIR = Path(__file__).resolve().parent


class Proxy:
    def __init__(self, esp32_url: str):
        self.esp32_url = esp32_url.rstrip("/")

    def get_state(self):
        with urlopen(self.esp32_url + "/api/state", timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))

    def post(self, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        request = Request(self.esp32_url + path, data=data,
                          headers={"Content-Type": "application/json"},
                          method="POST")
        with urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    proxy: Proxy | None = None

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path == "/api/state":
            try:
                self.send_json(self.proxy.get_state())
            except (OSError, URLError, ValueError) as exc:
                self.send_json({"connected": False, "error": str(exc)}, 503)
            return
        if self.path in ("/", "/index.html"):
            data = (DASHBOARD_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        if self.path not in ("/api/command", "/api/heartbeat"):
            self.send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = self.proxy.post(self.path, payload)
            self.send_json(result)
        except (OSError, URLError, ValueError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, 503)

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--esp32-ip", required=True,
                        help="ESP32 Wi-Fi address, for example 192.168.1.123")
    parser.add_argument("--http-port", type=int, default=8090)
    args = parser.parse_args()
    Handler.proxy = Proxy("http://{}".format(args.esp32_ip))
    server = ThreadingHTTPServer(("127.0.0.1", args.http_port), Handler)
    print("Wi-Fi dashboard: http://127.0.0.1:{}/".format(args.http_port))
    print("ESP32 API: {}".format(Handler.proxy.esp32_url))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
