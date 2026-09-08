#!/usr/bin/env python3
"""Local serial bridge and web dashboard server.

Run from simulator/:
    python dashboard/server.py --port /dev/cu.usbserial-020D143B

Then open http://127.0.0.1:8080.  Use --dry-run to preview the dashboard
without an ESP32 attached.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import serial
except ImportError as exc:  # pragma: no cover - exercised on user machines
    raise SystemExit("Install dashboard dependencies with: pip install pyserial") from exc


DASHBOARD_DIR = Path(__file__).resolve().parent
SIMULATOR_DIR = DASHBOARD_DIR.parent
if str(SIMULATOR_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SIMULATOR_DIR))

from dual_board.ripple_logic import FollowerController, ReferencePublisher


class SerialBridge:
    def __init__(self, port: str, baudrate: int = 115200, dry_run: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.dry_run = dry_run
        self.lock = threading.Lock()
        self.serial = None
        self.last_error = ""
        self.last_rx = 0.0
        self.samples: list[dict[str, Any]] = []
        self.sample_seq = 0
        self.sample_history_size = 1000
        self.state: dict[str, Any] = {
            "connected": False,
            "port": port,
            "baudrate": baudrate,
            "last_error": "",
            "last_rx": None,
            "ready": False,
            "sensor_found": False,
            "sensor": "BNO055",
            "telemetry_hz": 30,
            "imu": {"heading": 0, "roll": 0, "pitch": 0,
                    "accel": {"x": 0, "y": 0, "z": 0},
                    "gyro": {"x": 0, "y": 0, "z": 0},
                    "temperature_c": 0, "calibration": 0},
            "motor": {"running": False, "estopped": False, "rpm": 0, "target_rpm": 0,
                      "accel_rpm_s": 60, "mode": "idle",
                      "direction": 1, "position_steps": 0, "target_steps": 0,
                      "distance_rev": 0, "steps_per_rev": 3200,
                      "amplitude_rev": 0, "cycles": 0, "half_cycles": 0,
                      "intensity": 1.0,
                      "limits": {"min_rpm": 1, "max_rpm": 240,
                                 "min_accel_rpm_s": 1, "max_accel_rpm_s": 120,
                                 "max_step_rate": 15000}},
        }
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _append_sample(self, t_ms, imu):
        self.sample_seq += 1
        self.samples.append({
            "seq": self.sample_seq,
            "t_ms": t_ms,
            "heading": imu.get("heading", 0),
            "roll": imu.get("roll", 0),
            "pitch": imu.get("pitch", 0),
        })
        if len(self.samples) > self.sample_history_size:
            del self.samples[:-self.sample_history_size]

    def snapshot(self, since=0):
        with self.lock:
            snapshot = json.loads(json.dumps(self.state))
            snapshot["sample_seq"] = self.sample_seq
            snapshot["samples"] = [sample for sample in self.samples if sample["seq"] > since]
            return snapshot

    def _set(self, **values):
        with self.lock:
            self.state.update(values)

    def _reader(self):
        if self.dry_run:
            self._set(connected=True, ready=True, last_error="")
            start = time.monotonic()
            while not self.stop_event.wait(0.1):
                t = time.monotonic() - start
                with self.lock:
                    motor = self.state["motor"]
                    if motor["running"]:
                        motor["distance_rev"] += motor["rpm"] / 600.0
                        if motor["target_steps"]:
                            motor["position_steps"] += int(motor["rpm"] * 3200 / 600)
                            if abs(motor["position_steps"]) >= motor["target_steps"]:
                                motor["running"] = False
                    self.state["imu"] = {
                        "heading": (t * 12) % 360,
                        "roll": math.sin(t * 2.0) * 3.5,
                        "pitch": math.cos(t * 1.7) * 2.0,
                        "accel": {"x": math.sin(t) * 0.04, "y": 0.02, "z": 9.81},
                        "gyro": {"x": math.cos(t) * 2.0, "y": 0.3, "z": 12.0},
                        "temperature_c": 27,
                        "calibration": 0xFF,
                    }
                    self._append_sample(int(t * 1000), self.state["imu"])
                    self.state["last_rx"] = time.time()
            return

        while not self.stop_event.is_set():
            # USB serial devices can disappear when the board is reset or
            # replugged. Re-open the named device instead of leaving the
            # dashboard permanently disconnected after the first failure.
            if self.serial is None or not self.serial.is_open:
                try:
                    self.serial = serial.Serial(self.port, self.baudrate,
                                                timeout=0.2,
                                                write_timeout=0.5)
                    self._set(connected=True, ready=False,
                              sensor_found=False, last_error="")
                except Exception as exc:
                    self.last_error = str(exc)
                    self._set(connected=False, ready=False,
                              sensor_found=False, last_error=self.last_error)
                    self.stop_event.wait(1.0)
                    continue
            try:
                raw = self.serial.readline()
                if not raw:
                    continue
                try:
                    message = json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                self._consume(message)
            except Exception as exc:
                self.last_error = str(exc)
                self._set(connected=False, ready=False,
                          sensor_found=False, last_error=self.last_error)
                try:
                    self.serial.close()
                except Exception:
                    pass
                self.serial = None
                self.stop_event.wait(1.0)

    def _consume(self, message):
        with self.lock:
            self.state["last_rx"] = time.time()
            kind = message.get("type")
            if kind == "telemetry":
                self.state["imu"] = message.get("imu", self.state["imu"])
                self.state["motor"] = message.get("motor", self.state["motor"])
                self._append_sample(message.get("t_ms", 0), self.state["imu"])
                if "sensor_found" in message:
                    self.state["sensor_found"] = bool(message["sensor_found"])
                    if message["sensor_found"]:
                        self.state["ready"] = True
                if message.get("sensor"):
                    self.state["sensor"] = message["sensor"]
            elif kind == "ready":
                self.state["ready"] = True
                self.state["sensor_found"] = True
                self.state["sensor"] = message.get("sensor", "BNO055")
            elif kind in ("ack", "status"):
                if "motor" in message:
                    self.state["motor"] = message["motor"]
            elif kind == "error":
                self.state["last_error"] = message.get("message", "device error")

    def send(self, command: dict[str, Any]):
        with self.lock:
            if self.dry_run:
                name = command.get("cmd")
                motor = self.state["motor"]
                if name in ("run", "set"):
                    motor.update({"rpm": float(command.get("rpm", motor["rpm"])),
                                  "target_steps": int(float(command.get("distance_rev", 0)) * 3200),
                                  "direction": int(command.get("direction", 1))})
                    if name == "run":
                        motor["running"] = True
                elif name == "stop":
                    motor["running"] = False
                elif name == "estop":
                    motor.update({"running": False, "estopped": True})
                elif name == "clear_estop":
                    motor["estopped"] = False
                return
            if self.serial is None or not self.serial.is_open:
                raise RuntimeError("serial port is not connected")
            self.serial.write((json.dumps(command) + "\n").encode("utf-8"))

    def close(self):
        self.stop_event.set()
        if self.serial is not None:
            self.serial.close()


class MultiSerialBridge:
    """USB bridge for two boards with optional laptop-relayed peer motion."""

    def __init__(self, ports, baudrate=115200, peer_mode=False):
        self.bridges = {
            board_id: SerialBridge(port, baudrate)
            for board_id, port in ports.items()
        }
        self.peer_mode = bool(peer_mode)
        self.publishers = {
            board_id: ReferencePublisher(source=board_id)
            for board_id in self.bridges
        }
        self.followers = {}
        board_ids = list(self.bridges)
        if len(board_ids) == 2:
            left, right = board_ids
            self.followers[left] = FollowerController(source=right)
            self.followers[right] = FollowerController(source=left)
        self.peer_status = {
            "enabled": self.peer_mode,
            "delay_ms": 250,
            "target_fraction": 0.5,
            "last_commands": {},
        }
        self.stop_event = threading.Event()
        self.peer_thread = threading.Thread(target=self._peer_loop, daemon=True)
        self.peer_thread.start()

    def _peer_loop(self):
        while not self.stop_event.wait(0.05):
            if not self.peer_mode or len(self.bridges) != 2:
                continue
            now_ms = int(time.monotonic() * 1000)
            states = {
                board_id: bridge.snapshot()
                for board_id, bridge in self.bridges.items()
            }
            for board_id, state in states.items():
                if state.get("connected"):
                    packet = self.publishers[board_id].update(
                        state.get("imu", {}), now_ms
                    )
                    if packet is not None:
                        other_id = next(
                            candidate for candidate in self.bridges
                            if candidate != board_id
                        )
                        self.followers[other_id].receive(packet, now_ms)
            commands = {}
            for board_id, follower in self.followers.items():
                command = follower.tick(now_ms)
                if command is None or not states[board_id].get("connected"):
                    continue
                try:
                    self.bridges[board_id].send(command)
                    commands[board_id] = command
                except Exception as exc:
                    commands[board_id] = {"cmd": "error", "error": str(exc)}
            self.peer_status = {
                "enabled": True,
                "delay_ms": 250,
                "target_fraction": 0.5,
                "last_commands": commands,
                "followers": {
                    board_id: follower.status(now_ms)
                    for board_id, follower in self.followers.items()
                },
            }

    def snapshot(self, since=0):
        return {
            "connected": all(
                bridge.snapshot().get("connected")
                for bridge in self.bridges.values()
            ),
            "boards": {
                board_id: bridge.snapshot(since)
                for board_id, bridge in self.bridges.items()
            },
            "peer": self.peer_status,
        }

    def send(self, command):
        board_id = command.pop("board", next(iter(self.bridges)))
        if board_id not in self.bridges:
            raise ValueError("unknown board: {}".format(board_id))
        self.bridges[board_id].send(command)

    def close(self):
        self.stop_event.set()
        for bridge in self.bridges.values():
            bridge.close()


class DashboardHandler(BaseHTTPRequestHandler):
    bridge: SerialBridge | None = None

    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path == "/api/state":
            self._send_json(self.bridge.snapshot())
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            try:
                since = int(parse_qs(parsed.query).get("since", [0])[0])
            except ValueError:
                since = 0
            self._send_json(self.bridge.snapshot(max(0, since)))
            return
        if self.path in ("/", "/index.html"):
            data = (DASHBOARD_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        if self.path != "/api/command":
            self._send_json({"error": "not found"}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            command = json.loads(self.rfile.read(size))
            if command.get("cmd") not in {"run", "set", "rock", "peer_rock", "start", "stop", "estop", "clear_estop", "tare", "status"}:
                raise ValueError("unsupported command")
            self.bridge.send(command)
            self._send_json({"ok": True, "state": self.bridge.snapshot()})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 400)

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="ESP32 IMU/motor dashboard")
    parser.add_argument("--port", action="append",
                        help="serial device path; repeat for two boards")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--http-host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--dry-run", action="store_true", help="simulate device telemetry")
    parser.add_argument("--peer-mode", action="store_true",
                        help="relay filtered motion between two USB boards")
    args = parser.parse_args()

    ports = args.port or ["/dev/cu.usbserial-020D143B"]
    if args.dry_run or len(ports) == 1:
        bridge = SerialBridge(ports[0], args.baudrate, args.dry_run)
    else:
        bridge = MultiSerialBridge(
            {"egg-a": ports[0], "egg-b": ports[1]},
            args.baudrate,
            args.peer_mode,
        )
    DashboardHandler.bridge = bridge
    server = ThreadingHTTPServer((args.http_host, args.http_port), DashboardHandler)
    print("Wobble dashboard: http://{}:{}/".format(args.http_host, args.http_port))
    print("Serial: {} ({})".format(args.port, "dry-run" if args.dry_run else args.baudrate))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.close()
        server.server_close()


if __name__ == "__main__":
    main()
