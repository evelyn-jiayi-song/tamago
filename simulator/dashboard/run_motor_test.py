#!/usr/bin/env python3
"""Run one conservative motor test through the local dashboard bridge.

The dashboard must already be running and the motor must be mechanically clear.
Default command: 5 RPM, 0.25 revolution clockwise. The finally block sends a
stop command even if the script is interrupted.

Active firmware wiring:
    ESP32 GPIO25 -> TMC2209 STEP
    ESP32 GPIO26 -> TMC2209 DIR
    ESP32 GPIO27 -> TMC2209 ENN (active low)
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


def request(base_url: str, path: str, payload: Optional[dict] = None) -> dict:
    url = base_url.rstrip("/") + path
    if payload is None:
        req = Request(url, headers={"Cache-Control": "no-cache"})
    else:
        body = json.dumps(payload).encode("utf-8")
        req = Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json",
        })
    with urlopen(req, timeout=3) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a short TMC2209 motor test")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--rpm", type=float, default=5.0)
    parser.add_argument("--accel", type=float, default=60.0,
                        help="acceleration in RPM/s; default 60")
    parser.add_argument("--distance", type=float, default=0.25,
                        help="shaft revolutions; default 0.25")
    parser.add_argument("--direction", type=int, choices=(-1, 1), default=1)
    args = parser.parse_args()

    try:
        before = request(args.url, "/api/state")
    except URLError as exc:
        raise SystemExit("Dashboard unavailable at {}: {}".format(args.url, exc))

    if not before.get("connected") or not before.get("ready"):
        raise SystemExit("ESP32 is not ready; check the dashboard connection first")
    if before.get("motor", {}).get("estopped"):
        raise SystemExit("Motor is e-stopped; clear it from the dashboard first")
    if before.get("motor", {}).get("running"):
        raise SystemExit("Motor is already running; stop it from the dashboard first")

    command = {"cmd": "run", "rpm": args.rpm, "accel": args.accel,
               "distance_rev": args.distance, "direction": args.direction}
    result = request(args.url, "/api/command", command)
    if not result.get("ok"):
        raise SystemExit("Motor command rejected: {}".format(result.get("error")))

    print("Started: {} RPM for {} revolution(s)".format(args.rpm, args.distance))
    start_time = time.monotonic()
    ramp_seconds = (max(0.0, args.rpm - 1.0) / args.accel) if args.accel > 0 else 0
    expected_seconds = ((args.distance / args.rpm * 60.0) if args.rpm > 0 else 0) + ramp_seconds
    deadline = start_time + max(5.0, expected_seconds + 3.0)
    seen_running = False
    try:
        while time.monotonic() < deadline:
            state = request(args.url, "/api/state")
            motor = state.get("motor", {})
            if motor.get("running"):
                seen_running = True
            print("\rposition={:.3f} rev  running={}".format(
                float(motor.get("distance_rev", 0)), motor.get("running")), end="", flush=True)
            if seen_running and not motor.get("running"):
                break
            time.sleep(0.1)
        if not seen_running:
            raise SystemExit("No running acknowledgment received from the ESP32")
    except KeyboardInterrupt:
        print("\nInterrupted; stopping motor")
    finally:
        request(args.url, "/api/command", {"cmd": "stop"})
    print("\nMotor test complete; stop command sent")


if __name__ == "__main__":
    main()
