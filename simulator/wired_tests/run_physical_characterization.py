#!/usr/bin/env python3
"""Staged physical characterization through the existing USB dashboard.

This script never resets, uploads, or erases the ESP32. It sends only bounded
motor commands through the already-running dashboard bridge and always sends a
stop command in ``finally``. Results are written to a separate JSON log.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from urllib.request import Request, urlopen


def request(base_url: str, path: str, payload: dict | None = None) -> dict:
    url = base_url.rstrip("/") + path
    if payload is None:
        req = Request(url, headers={"Cache-Control": "no-cache"})
    else:
        req = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                      headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=3) as response:
        return json.load(response)


def snapshot(state: dict, host_time: float) -> dict:
    imu = state.get("imu", {})
    gyro = imu.get("gyro", {})
    motor = state.get("motor", {})
    return {
        "host_time": host_time,
        "sample_seq": state.get("sample_seq"),
        "imu": {
            "heading": float(imu.get("heading", 0.0)),
            "roll": float(imu.get("roll", 0.0)),
            "pitch": float(imu.get("pitch", 0.0)),
            "gyro": {axis: float(gyro.get(axis, 0.0)) for axis in "xyz"},
            "temperature_c": float(imu.get("temperature_c", 0.0)),
            "calibration": imu.get("calibration"),
        },
        "motor": {
            "running": bool(motor.get("running")),
            "mode": motor.get("mode"),
            "rpm": float(motor.get("rpm", 0.0)),
            "target_rpm": float(motor.get("target_rpm", 0.0)),
            "position_steps": int(motor.get("position_steps", 0) or 0),
            "distance_rev": float(motor.get("distance_rev", 0.0)),
            "direction": int(motor.get("direction", 1) or 1),
            "estopped": bool(motor.get("estopped")),
        },
    }


def extrema(samples: list[dict]) -> dict:
    if not samples:
        return {}
    result = {}
    for axis in ("heading", "roll", "pitch"):
        values = [row["imu"][axis] for row in samples]
        result[axis] = {
            "min": min(values),
            "max": max(values),
            "peak_abs": max(abs(value) for value in values),
        }
    gyro_values = [math.sqrt(sum(row["imu"]["gyro"][axis] ** 2 for axis in "xyz"))
                   for row in samples]
    result["gyro_vector_dps"] = {"peak_abs": max(gyro_values)}
    result["temperature_c"] = {
        "min": min(row["imu"]["temperature_c"] for row in samples),
        "max": max(row["imu"]["temperature_c"] for row in samples),
    }
    return result


def run_case(base_url: str, name: str, command: dict, active_s: float,
             wait_for_auto_stop: bool, interval_s: float) -> dict:
    request(base_url, "/api/command", {"cmd": "tare"})
    time.sleep(0.2)
    before = request(base_url, "/api/state")
    if before.get("motor", {}).get("running"):
        raise RuntimeError("motor was already running before case {}".format(name))

    started = time.monotonic()
    result = request(base_url, "/api/command", command)
    if not result.get("ok"):
        raise RuntimeError("case {} rejected: {}".format(name, result))

    samples = []
    seen_running = False
    stop_sent = None
    stopped = None
    deadline = started + active_s + (8.0 if wait_for_auto_stop else 2.0)
    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            state = request(base_url, "/api/state")
            samples.append(snapshot(state, now))
            running = state.get("motor", {}).get("running", False)
            seen_running = seen_running or running
            if wait_for_auto_stop and seen_running and not running:
                stopped = now
                break
            if not wait_for_auto_stop and stop_sent is None and now - started >= active_s:
                request(base_url, "/api/command", {"cmd": "stop"})
                stop_sent = time.monotonic()
            if stop_sent is not None and not running:
                stopped = now
                break
            time.sleep(interval_s)
    finally:
        if stop_sent is None and not (wait_for_auto_stop and stopped is not None):
            request(base_url, "/api/command", {"cmd": "stop"})
            stop_sent = time.monotonic()
        if stopped is None:
            state = request(base_url, "/api/state")
            samples.append(snapshot(state, time.monotonic()))
            if not state.get("motor", {}).get("running", False):
                stopped = time.monotonic()

    return {
        "name": name,
        "command": command,
        "started_host_time": started,
        "stop_command_host_time": stop_sent,
        "stopped_host_time": stopped,
        "stop_latency_s": ((stopped - stop_sent) if stopped is not None and stop_sent is not None else None),
        "sample_count": len(samples),
        "observed": extrema(samples),
        "samples": samples,
    }


def run_reverse_case(base_url: str, interval_s: float) -> dict:
    name = "reverse_while_sustaining"
    command = {"cmd": "rock", "rpm": 8, "accel": 30,
               "amplitude_rev": 0.08, "cycles": 0}
    request(base_url, "/api/command", {"cmd": "tare"})
    time.sleep(0.2)
    started = time.monotonic()
    result = request(base_url, "/api/command", command)
    if not result.get("ok"):
        raise RuntimeError("case {} rejected: {}".format(name, result))

    samples = []
    reverse_time = None
    stop_sent = None
    stopped = None
    try:
        while time.monotonic() - started < 1.0:
            now = time.monotonic()
            samples.append(snapshot(request(base_url, "/api/state"), now))
            time.sleep(interval_s)
        reverse_time = time.monotonic()
        reverse = request(base_url, "/api/command", {
            "cmd": "set", "rpm": 8, "accel": 30, "direction": -1,
        })
        if not reverse.get("ok"):
            raise RuntimeError("reverse command rejected: {}".format(reverse))
        while time.monotonic() - reverse_time < 1.0:
            now = time.monotonic()
            samples.append(snapshot(request(base_url, "/api/state"), now))
            time.sleep(interval_s)
        request(base_url, "/api/command", {"cmd": "stop"})
        stop_sent = time.monotonic()
        while time.monotonic() - stop_sent < 2.0:
            now = time.monotonic()
            state = request(base_url, "/api/state")
            samples.append(snapshot(state, now))
            if not state.get("motor", {}).get("running", False):
                stopped = now
                break
            time.sleep(interval_s)
    finally:
        if stop_sent is None:
            request(base_url, "/api/command", {"cmd": "stop"})
            stop_sent = time.monotonic()
        if stopped is None:
            state = request(base_url, "/api/state")
            samples.append(snapshot(state, time.monotonic()))
            if not state.get("motor", {}).get("running", False):
                stopped = time.monotonic()

    return {
        "name": name,
        "command": command,
        "reverse_command": {"cmd": "set", "rpm": 8, "accel": 30, "direction": -1},
        "started_host_time": started,
        "reverse_host_time": reverse_time,
        "stop_command_host_time": stop_sent,
        "stopped_host_time": stopped,
        "stop_latency_s": ((stopped - stop_sent) if stopped is not None and stop_sent is not None else None),
        "sample_count": len(samples),
        "observed": extrema(samples),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="simulator/wired_tests/physical_characterization.json")
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("--case", choices=("finite_low_speed", "full_circle_run",
                                             "full_circle_reverse",
                                             "rock_once_low_speed",
                                             "sustain_then_stop", "reverse_while_sustaining",
                                             "half_intensity"),
                        help="run one case only; omit to run the full staged suite")
    args = parser.parse_args()
    if args.interval <= 0:
        raise SystemExit("interval must be positive")

    initial = request(args.url, "/api/state")
    if not initial.get("connected") or not initial.get("ready") or not initial.get("sensor_found"):
        raise SystemExit("ESP32/BNO055 is not ready")
    if initial.get("motor", {}).get("running"):
        raise SystemExit("motor is already running")
    if initial.get("motor", {}).get("estopped"):
        raise SystemExit("motor is e-stopped; clear it manually first")

    cases = [
        ("finite_low_speed", {
            "cmd": "run", "rpm": 3, "accel": 20, "distance_rev": 0.05, "direction": 1,
        }, 3.0, True),
        ("full_circle_run", {
            "cmd": "run", "rpm": 3, "accel": 20, "distance_rev": 1.0, "direction": 1,
        }, 25.0, True),
        ("full_circle_reverse", {
            "cmd": "run", "rpm": 3, "accel": 20, "distance_rev": 1.0, "direction": -1,
        }, 25.0, True),
        ("rock_once_low_speed", {
            "cmd": "rock", "rpm": 4, "accel": 20, "amplitude_rev": 0.05, "cycles": 1,
        }, 4.0, True),
        ("sustain_then_stop", {
            "cmd": "rock", "rpm": 8, "accel": 30, "amplitude_rev": 0.08, "cycles": 0,
        }, 1.5, False),
        ("reverse_while_sustaining", {
            "cmd": "rock", "rpm": 8, "accel": 30, "amplitude_rev": 0.08, "cycles": 0,
        }, 1.0, False),
        ("half_intensity", {
            "cmd": "rock", "rpm": 12, "accel": 30, "amplitude_rev": 0.10,
            "cycles": 2, "intensity": 0.5,
        }, 5.0, True),
    ]
    if args.case:
        cases = [case for case in cases if case[0] == args.case]

    runs = []
    for name, command, active_s, auto_stop in cases:
        if name == "reverse_while_sustaining":
            print("Running {}: {}".format(name, command), flush=True)
            runs.append(run_reverse_case(args.url, args.interval))
            continue
        print("Running {}: {}".format(name, command), flush=True)
        runs.append(run_case(args.url, name, command, active_s, auto_stop, args.interval))

    output = {
        "test": "wired_egg_physical_characterization",
        "dashboard_url": args.url,
        "limits_from_initial_state": initial.get("motor", {}).get("limits"),
        "runs": runs,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("Wrote {} cases to {}".format(len(runs), output_path))


if __name__ == "__main__":
    main()
