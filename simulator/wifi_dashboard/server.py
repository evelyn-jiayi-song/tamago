#!/usr/bin/env python3
"""Laptop proxy for the separate ESP32 Wi-Fi dashboard experiment."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


DASHBOARD_DIR = Path(__file__).resolve().parent
SIMULATOR_DIR = DASHBOARD_DIR.parent
if str(SIMULATOR_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATOR_DIR))

from dual_board.ripple_logic import FollowerController, ReferencePublisher


class PeerRelay:
    """Relay filtered motion between boards through the laptop proxy."""

    def __init__(self, board_ids):
        self.board_ids = list(board_ids)
        self.enabled = False
        self.publishers = {
            board_id: ReferencePublisher(source=board_id)
            for board_id in self.board_ids
        }
        self.followers = {}
        if len(self.board_ids) == 2:
            left, right = self.board_ids
            self.followers[left] = FollowerController(source=right)
            self.followers[right] = FollowerController(source=left)
        self.lock = threading.Lock()
        self.last_status = {
            "enabled": False,
            "delay_ms": 250,
            "target_fraction": 0.5,
            "last_commands": {},
        }

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled = bool(enabled)
            if not self.enabled:
                self.last_status["last_commands"] = {}

    def status(self):
        with self.lock:
            return dict(self.last_status, enabled=self.enabled)

    def relay(self, states, post_command):
        """Process current board states and issue only new peer commands."""
        with self.lock:
            if not self.enabled or len(self.board_ids) != 2:
                return
            now_ms = int(time.monotonic() * 1000)
            for board_id in self.board_ids:
                state = states.get(board_id, {})
                if state.get("connected") is not False:
                    packet = self.publishers[board_id].update(
                        state.get("imu", {}), now_ms
                    )
                    if packet is not None:
                        other_id = next(
                            candidate for candidate in self.board_ids
                            if candidate != board_id
                        )
                        self.followers[other_id].receive(packet, now_ms)

            commands = {}
            for board_id, follower in self.followers.items():
                command = follower.tick(now_ms)
                if command is not None and states.get(board_id, {}).get("connected"):
                    try:
                        post_command(board_id, command)
                        commands[board_id] = command
                    except (OSError, URLError, ValueError) as exc:
                        commands[board_id] = {
                            "cmd": "error",
                            "error": str(exc),
                        }
            self.last_status = {
                "enabled": True,
                "delay_ms": 250,
                "target_fraction": 0.5,
                "last_commands": commands,
                "followers": {
                    board_id: follower.status(now_ms)
                    for board_id, follower in self.followers.items()
                },
            }


class Proxy:
    def __init__(self, boards):
        self.boards = {
            board_id: url.rstrip("/") for board_id, url in boards.items()
        }
        self.peer = PeerRelay(self.boards)

    def _request(self, board_id, method, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            self.boards[board_id] + path,
            data=data,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_state(self):
        states = {}
        for board_id in self.boards:
            try:
                state = self._request(board_id, "GET", "/api/state")
                state["connected"] = True
            except (OSError, URLError, ValueError) as exc:
                state = {"connected": False, "error": str(exc)}
            states[board_id] = state
        self.peer.relay(states, lambda board_id, command:
                        self._request(board_id, "POST", "/api/command", command))
        return {
            "connected": all(state.get("connected") for state in states.values()),
            "boards": states,
            "peer": self.peer.status(),
        }

    def post(self, path: str, payload: dict):
        if path == "/api/heartbeat":
            results = {}
            for board_id in self.boards:
                try:
                    results[board_id] = self._request(
                        board_id, "POST", path, payload
                    )
                except (OSError, URLError, ValueError) as exc:
                    results[board_id] = {"ok": False, "error": str(exc)}
            return {"ok": any(result.get("ok") for result in results.values()),
                    "boards": results}
        board_id = payload.pop("board", next(iter(self.boards)))
        if board_id not in self.boards:
            raise ValueError("unknown board: {}".format(board_id))
        return self._request(board_id, "POST", path, payload)


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
        if self.path == "/api/peer":
            self.send_json(self.proxy.peer.status())
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
        if self.path not in ("/api/command", "/api/heartbeat", "/api/peer"):
            self.send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/peer":
                self.proxy.peer.set_enabled(payload.get("enabled", False))
                self.send_json(self.proxy.peer.status())
                return
            result = self.proxy.post(self.path, payload)
            self.send_json(result)
        except (OSError, URLError, ValueError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, 503)

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--esp32-ip", action="append", required=True,
        help="ESP32 address; use BOARD=IP twice for two eggs",
    )
    parser.add_argument(
        "--peer-mode", action="store_true",
        help="Enable laptop-relayed peer motion at startup",
    )
    parser.add_argument("--http-port", type=int, default=8090)
    args = parser.parse_args()
    boards = {}
    for index, value in enumerate(args.esp32_ip, 1):
        if "=" in value:
            board_id, address = value.split("=", 1)
        else:
            board_id, address = "egg{}".format(index), value
        if not board_id or not address:
            parser.error("--esp32-ip must be IP or BOARD=IP")
        boards[board_id] = "http://{}".format(address)
    Handler.proxy = Proxy(boards)
    Handler.proxy.peer.set_enabled(args.peer_mode)
    server = ThreadingHTTPServer(("127.0.0.1", args.http_port), Handler)
    print("Wi-Fi dashboard: http://127.0.0.1:{}/".format(args.http_port))
    print("ESP32 boards: {}".format(", ".join(
        "{}={}".format(board_id, url)
        for board_id, url in Handler.proxy.boards.items()
    )))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
