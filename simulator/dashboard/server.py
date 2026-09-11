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

from dual_board.ripple_logic import (
    FollowerController,
    PeerEchoGate,
    ReferencePublisher,
    motion_features,
)


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
                      "absolute_position_steps": 0, "origin_steps": None,
                      "origin_recorded": False,
                      "distance_rev": 0, "steps_per_rev": 3200,
                      "amplitude_rev": 0, "cycles": 0, "half_cycles": 0,
                      "stable_tilt_deg": 0, "stable_max_tilt_deg": 15,
                      "stable_rpm_limit": 0, "safety_stop_reason": "",
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
                if name in ("run", "smooth_run", "set"):
                    motor.update({"rpm": float(command.get("rpm", motor["rpm"])),
                                  "target_steps": int(float(command.get("distance_rev", 0)) * 3200),
                                  "direction": int(command.get("direction", 1))})
                    if name == "run":
                        motor["running"] = True
                elif name == "stop":
                    motor["running"] = False
                elif name == "set_origin":
                    if motor["running"]:
                        raise RuntimeError("stop the motor before recording origin")
                    motor["origin_steps"] = motor.get("absolute_position_steps", 0)
                    motor["origin_recorded"] = True
                elif name == "return_origin":
                    if not motor.get("origin_recorded"):
                        raise RuntimeError("origin has not been recorded")
                    if motor["running"]:
                        raise RuntimeError("stop the motor before returning to origin")
                    steps = int(round(
                        (motor["origin_steps"] -
                         motor.get("absolute_position_steps", 0)) % 3200
                    ))
                    motor.update({
                        "running": steps > 0,
                        "target_steps": steps,
                        "direction": 1,
                        "rpm": float(command.get("rpm", 10)),
                    })
                elif name == "estop":
                    motor.update({"running": False, "estopped": False})
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
        self.echo_gates = {
            board_id: PeerEchoGate()
            for board_id in self.bridges
        }
        self.peer_status = {
            "enabled": self.peer_mode,
            "delay_ms": 250,
            "target_fraction": 0.5,
            "source_response_gain": 3.0,
            "peer_severity_gain": 1.5,
            "peer_amplitude_rev": 3.0,
            "base_rpm": 100.0,
            "base_accel_rpm_s": 50.0,
            "reaction_speed_gain": 1.5,
            "reaction_accel_gain": 1.5,
            "peer_cycles": 2,
            "last_commands": {},
            "sources": {},
        }
        self.last_peer_commands = {}
        self.last_peer_send_ms = {}
        self.stop_event = threading.Event()
        self.peer_thread = threading.Thread(target=self._peer_loop, daemon=True)
        self.peer_thread.start()

    def set_peer(self, enabled=None, target_fraction=None):
        was_enabled = self.peer_mode
        if enabled is not None:
            self.peer_mode = bool(enabled)
        if target_fraction is not None:
            fraction = float(target_fraction)
            if not 0 <= fraction <= 1:
                raise ValueError("target_fraction must be between 0 and 1")
            for follower in self.followers.values():
                follower.target_fraction = fraction
        self.peer_status["enabled"] = self.peer_mode
        self.peer_status["target_fraction"] = (
            next(iter(self.followers.values())).target_fraction
            if self.followers else 0.5
        )
        if was_enabled and not self.peer_mode:
            now_ms = int(time.monotonic() * 1000)
            for board_id, previous in list(self.last_peer_commands.items()):
                if not previous or previous.get("cmd") != "rock":
                    continue
                try:
                    self.bridges[board_id].send({
                        "cmd": "stop",
                        "reason": "peer_disabled",
                    })
                    self.echo_gates[board_id].trigger(now_ms, {
                        "cmd": "stop",
                        "reason": "peer_disabled",
                    })
                except Exception:
                    # A disconnected board will report its state separately;
                    # do not block disabling peer mode for the other board.
                    pass
            for follower in self.followers.values():
                follower.last_command = None
                follower.pending = []
            self.peer_status["last_commands"] = {}
            self.last_peer_commands.clear()
            self.last_peer_send_ms.clear()
        return self.peer_status

    def _peer_loop(self):
        while not self.stop_event.wait(0.05):
            if not self.peer_mode or len(self.bridges) != 2:
                continue
            now_ms = int(time.monotonic() * 1000)
            states = {
                board_id: bridge.snapshot()
                for board_id, bridge in self.bridges.items()
            }
            sources = {}
            for board_id, state in states.items():
                echo_suppressed = self.echo_gates[board_id].is_suppressed(now_ms)
                sources[board_id] = {
                    "echo_suppressed": echo_suppressed,
                }
                fresh = (
                    state.get("connected")
                    and state.get("last_rx") is not None
                    and time.time() - state["last_rx"] < 0.5
                )
                if fresh:
                    features = motion_features(state.get("imu", {}))
                    publisher = self.publishers[board_id]
                    packet = self.publishers[board_id].update(
                        state.get("imu", {}), now_ms
                    )
                    sources[board_id].update({
                        "gyro_dps": round(features["gyro_dps"], 2),
                        "dynamic_accel_mps2": round(
                            features["dynamic_accel_mps2"], 2
                        ),
                        "intensity": round(publisher.filter.intensity, 3),
                        "active": publisher.filter.active,
                    })
                    # Always update the local filter, but do not forward
                    # motion while this board is reacting to its peer.
                    if packet is not None and not echo_suppressed:
                        other_id = next(
                            candidate for candidate in self.bridges
                            if candidate != board_id
                        )
                        self.followers[other_id].receive(packet, now_ms)
            commands = {}
            for board_id, follower in self.followers.items():
                command = follower.tick(now_ms)
                target_fresh = (
                    states[board_id].get("connected")
                    and states[board_id].get("last_rx") is not None
                    and time.time() - states[board_id]["last_rx"] < 0.5
                )
                if command is None:
                    continue
                # A stop is safety-critical and should still be attempted if
                # telemetry has gone stale; a new motion command requires a
                # fresh target board before it is sent.
                if command.get("cmd") != "stop" and not target_fresh:
                    continue
                previous = self.last_peer_commands.get(board_id)
                # The firmware starts a new ramp whenever it receives a
                # ``rock`` command. Do not resend every filtered IMU packet:
                # repeated starts keep the motor near its minimum RPM.
                if (command.get("cmd") == "rock" and previous is not None and
                        previous.get("cmd") == "rock"):
                    intensity_delta = abs(
                        float(command.get("intensity", 0.0)) -
                        float(previous.get("intensity", 0.0))
                    )
                    if intensity_delta < 0.05:
                        commands[board_id] = previous
                        continue
                if (command.get("cmd") == "rock" and
                        previous is not None and
                        command.get("source_seq") != previous.get("source_seq") and
                        now_ms - self.last_peer_send_ms.get(board_id, 0) < 120):
                    continue
                try:
                    outgoing = dict(command)
                    # FollowerController already scales RPM/amplitude. The
                    # existing firmware scales rock commands by intensity,
                    # so use unity here to avoid applying the fraction twice.
                    if outgoing.get("cmd") == "rock":
                        outgoing["intensity"] = 1.0
                    self.bridges[board_id].send(outgoing)
                    self.echo_gates[board_id].trigger(now_ms, outgoing)
                    self.last_peer_commands[board_id] = command
                    self.last_peer_send_ms[board_id] = now_ms
                    commands[board_id] = command
                except Exception as exc:
                    commands[board_id] = {"cmd": "error", "error": str(exc)}
            self.peer_status = {
                "enabled": self.peer_mode,
                "delay_ms": 250,
                "target_fraction": 0.5,
                "source_response_gain": (
                    next(iter(self.followers.values())).source_response_gain
                    if self.followers else 3.0
                ),
                "peer_severity_gain": (
                    next(iter(self.followers.values())).peer_severity_gain
                    if self.followers else 1.5
                ),
                "peer_amplitude_rev": (
                    next(iter(self.followers.values())).base_amplitude_rev
                    if self.followers else 3.0
                ),
                "base_rpm": (
                    next(iter(self.followers.values())).base_rpm
                    if self.followers else 100.0
                ),
                "base_accel_rpm_s": (
                    next(iter(self.followers.values())).base_accel_rpm_s
                    if self.followers else 50.0
                ),
                "reaction_speed_gain": (
                    next(iter(self.followers.values())).reaction_speed_gain
                    if self.followers else 1.5
                ),
                "reaction_accel_gain": (
                    next(iter(self.followers.values())).reaction_accel_gain
                    if self.followers else 1.5
                ),
                "peer_cycles": (
                    next(iter(self.followers.values())).peer_cycles
                    if self.followers else 2
                ),
                "last_commands": commands,
                "sources": sources,
                "followers": {
                    board_id: follower.status(now_ms)
                    for board_id, follower in self.followers.items()
                },
                "echo_gates": {
                    board_id: gate.status(now_ms)
                    for board_id, gate in self.echo_gates.items()
                },
            }
            if self.followers:
                self.peer_status["target_fraction"] = next(
                    iter(self.followers.values())
                ).target_fraction

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
        if self.path not in ("/api/command", "/api/peer"):
            self._send_json({"error": "not found"}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size))
            if self.path == "/api/peer":
                self._send_json(self.bridge.set_peer(
                    enabled=payload.get("enabled"),
                    target_fraction=payload.get("target_fraction"),
                ))
                return
            command = payload
            if command.get("cmd") not in {"run", "smooth_run", "set", "rock", "smooth_rock", "stable_rock", "peer_rock", "start", "stop", "estop", "clear_estop", "tare", "set_origin", "return_origin", "status"}:
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
    if args.dry_run:
        bridge = SerialBridge(ports[0], args.baudrate, args.dry_run)
    elif len(ports) == 1:
        # Keep the two-egg UI shape when only one USB board is available.
        bridge = MultiSerialBridge(
            {"egg-b": ports[0]},
            args.baudrate,
            False,
        )
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
