#!/usr/bin/env python3
"""Read-only USB telemetry capture for the existing one-board system.

This script only performs GET /api/state requests. It never sends a motor
command, reset, upload, or erase operation.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from urllib.request import Request, urlopen


def get_state(base_url: str) -> dict:
    request = Request(base_url.rstrip("/") + "/api/state",
                      headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=3) as response:
        return json.load(response)


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture read-only USB telemetry")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("--output", default="simulator/wired_tests/usb_capture.json")
    args = parser.parse_args()
    if args.duration <= 0 or args.interval <= 0:
        raise SystemExit("duration and interval must be positive")

    samples = []
    errors = []
    started = time.monotonic()
    while time.monotonic() - started < args.duration:
        host_time = time.time()
        try:
            state = get_state(args.url)
            imu = state.get("imu", {})
            gyro = imu.get("gyro", {})
            accel = imu.get("accel", {})
            motor = state.get("motor", {})
            samples.append({
                "host_time": host_time,
                "sample_seq": state.get("sample_seq"),
                "imu": {
                    "heading": number(imu.get("heading")),
                    "roll": number(imu.get("roll")),
                    "pitch": number(imu.get("pitch")),
                    "gyro": {axis: number(gyro.get(axis)) for axis in "xyz"},
                    "accel": {axis: number(accel.get(axis)) for axis in "xyz"},
                    "temperature_c": number(imu.get("temperature_c")),
                    "calibration": imu.get("calibration"),
                },
                "motor": {
                    "running": bool(motor.get("running")),
                    "mode": motor.get("mode"),
                    "rpm": number(motor.get("rpm")),
                    "target_rpm": number(motor.get("target_rpm")),
                    "position_steps": motor.get("position_steps"),
                    "distance_rev": number(motor.get("distance_rev")),
                    "direction": motor.get("direction"),
                    "estopped": bool(motor.get("estopped")),
                },
            })
        except Exception as exc:
            errors.append({"host_time": host_time, "error": repr(exc)})
        time.sleep(args.interval)

    angles = {axis: [row["imu"][axis] for row in samples]
              for axis in ("heading", "roll", "pitch")}
    rates = {axis: [row["imu"]["gyro"][axis] for row in samples]
             for axis in "xyz"}
    intervals_ms = [1000.0 * (b["host_time"] - a["host_time"])
                    for a, b in zip(samples, samples[1:])]
    summary = {
        "sample_count": len(samples),
        "error_count": len(errors),
        "duration_s": args.duration,
        "poll_interval_s": args.interval,
        "angle_range_deg": {
            axis: {"min": min(values), "max": max(values),
                   "span": max(values) - min(values)}
            for axis, values in angles.items() if values
        },
        "gyro_range_dps": {
            axis: {"min": min(values), "max": max(values),
                   "peak_abs": max(abs(value) for value in values)}
            for axis, values in rates.items() if values
        },
        "poll_interval_ms": {
            "median": statistics.median(intervals_ms) if intervals_ms else None,
            "max": max(intervals_ms) if intervals_ms else None,
        },
        "motor_running_samples": sum(row["motor"]["running"] for row in samples),
        "last_state": samples[-1] if samples else None,
    }
    output = {"summary": summary, "errors": errors, "samples": samples}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Wrote {} samples to {}".format(len(samples), output_path))


if __name__ == "__main__":
    main()
