#!/usr/bin/env python3
"""Interactive IMU-feedback rocker using the local dashboard bridge.

The IMU must be mounted on the moving weight. The script tares at rest, starts
continuous low-speed rotation, then adjusts direction and target RPM from the
relative roll or pitch angle. It always sends stop on exit.

This is a commissioning controller, not a guaranteed-stable physical model.
Begin with a small target angle, low RPM, and no attached load.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Optional
from urllib.request import Request, urlopen


def request(base_url: str, path: str, payload: Optional[dict] = None) -> dict:
    url = base_url.rstrip("/") + path
    if payload is None:
        req = Request(url, headers={"Cache-Control": "no-cache"})
    else:
        req = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                      headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=3) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune rocking from relative IMU angle")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--axis", choices=("roll", "pitch"), default="pitch")
    parser.add_argument("--gyro-axis", choices=("x", "y"), default=None)
    parser.add_argument("--target-angle", type=float, default=8.0,
                        help="rock angle in degrees; default 8")
    parser.add_argument("--rpm", type=float, default=20.0,
                        help="nominal RPM; default 20")
    parser.add_argument("--max-rpm", type=float, default=60.0,
                        help="feedback ceiling; default 60")
    parser.add_argument("--min-rpm", type=float, default=1.0)
    parser.add_argument("--accel", type=float, default=30.0,
                        help="RPM/s; default 30")
    parser.add_argument("--kp", type=float, default=3.0,
                        help="RPM per degree of angle error")
    parser.add_argument("--kd", type=float, default=0.4,
                        help="RPM per degree/s of angular-rate damping")
    parser.add_argument("--duration", type=float, default=10.0,
                        help="seconds; default 10")
    parser.add_argument("--no-tare", action="store_true",
                        help="use the current relative reference")
    args = parser.parse_args()

    if args.target_angle <= 0 or args.min_rpm <= 0 or args.max_rpm < args.min_rpm:
        raise SystemExit("target-angle must be positive and max-rpm >= min-rpm > 0")
    gyro_axis = args.gyro_axis or ("x" if args.axis == "roll" else "y")

    state = request(args.url, "/api/state")
    if not state.get("connected") or not state.get("ready") or not state.get("sensor_found"):
        raise SystemExit("ESP32/BNO055 is not ready")
    if state.get("motor", {}).get("running"):
        raise SystemExit("Motor is already running; stop it first")

    if not args.no_tare:
        tare = request(args.url, "/api/command", {"cmd": "tare"})
        if not tare.get("ok"):
            raise SystemExit("Tare failed: {}".format(tare.get("error", "unknown error")))
        time.sleep(0.15)

    direction = 1
    last_rpm = args.min_rpm
    request(args.url, "/api/command", {
        "cmd": "run", "rpm": last_rpm, "accel": args.accel,
        "distance_rev": 0, "direction": direction,
    })
    started = time.monotonic()
    next_command = 0.0
    print("Feedback rocker started; Ctrl-C or timeout sends stop")
    try:
        while time.monotonic() - started < args.duration:
            state = request(args.url, "/api/state")
            if not state.get("connected") or not state.get("sensor_found"):
                raise RuntimeError("IMU/ESP32 connection lost")
            imu = state.get("imu", {})
            angle = float(imu.get(args.axis, 0.0))
            gyro = float(imu.get("gyro", {}).get(gyro_axis, 0.0))
            if angle >= args.target_angle:
                direction = -1
            elif angle <= -args.target_angle:
                direction = 1
            angle_error = max(0.0, args.target_angle - abs(angle))
            rpm = args.rpm + args.kp * angle_error - args.kd * abs(gyro)
            rpm = max(args.min_rpm, min(args.max_rpm, rpm))
            if time.monotonic() >= next_command and (abs(rpm - last_rpm) >= 1.0):
                request(args.url, "/api/command", {
                    "cmd": "set", "rpm": rpm, "accel": args.accel,
                    "direction": direction,
                })
                last_rpm = rpm
                next_command = time.monotonic() + 0.1
            print("\r{}={:+6.2f}° gyro{}={:+6.2f} rpm={:5.1f} dir={:+d}".format(
                args.axis, angle, gyro_axis, gyro, rpm, direction), end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        request(args.url, "/api/command", {"cmd": "stop"})
    print("\nFeedback rocker stopped")


if __name__ == "__main__":
    main()
