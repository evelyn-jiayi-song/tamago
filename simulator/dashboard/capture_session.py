#!/usr/bin/env python3
"""Run a dashboard command and save synchronized telemetry for plotting.

Examples:
    python dashboard/capture_session.py --board egg-a --mode smooth \
        --rpm 20 --accel 20 --distance 1 --output results/egg-a-smooth.json
    python dashboard/capture_session.py --board both --mode run \
        --rpm 5 --accel 10 --distance .05
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


def request(base_url: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    with urlopen(Request(base_url + path, data=data, headers=headers,
                         method="POST" if payload is not None else "GET"),
                 timeout=3) as response:
        return json.loads(response.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8090")
    parser.add_argument("--board", choices=("egg-a", "egg-b", "both"),
                        default="egg-a")
    parser.add_argument("--mode", choices=("run", "smooth", "rock", "balanced"),
                        default="smooth")
    parser.add_argument("--rpm", type=float, default=10)
    parser.add_argument("--accel", type=float, default=10)
    parser.add_argument("--distance", type=float, default=0.05)
    parser.add_argument("--amplitude", type=float, default=0.05)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    board_ids = ("egg-a", "egg-b") if args.board == "both" else (args.board,)
    output = args.output or Path(
        "results/session-{}.json".format(time.strftime("%Y%m%d-%H%M%S"))
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    command = {
        "cmd": ("smooth_rock" if args.mode == "balanced" else
                ("rock" if args.mode == "rock" else
                 ("smooth_run" if args.mode == "smooth" else "run"))),
        "rpm": args.rpm,
        "accel": args.accel,
        "distance_rev": args.distance,
        "amplitude_rev": args.amplitude,
        "cycles": args.cycles,
        "direction": 1,
    }
    start = time.monotonic()
    samples = []
    sent = []
    while True:
        state = request(args.dashboard_url, "/api/state")
        boards = state.get("boards", {})
        if all(boards.get(board, {}).get("connected") for board in board_ids):
            break
        if time.monotonic() - start > args.timeout:
            raise TimeoutError("selected board did not connect")
        time.sleep(0.25)

    for board in board_ids:
        sent_command = dict(command, board=board)
        request(args.dashboard_url, "/api/command", sent_command)
        sent.append(sent_command)

    completed = False
    saw_running = {board: False for board in board_ids}
    while time.monotonic() - start <= args.timeout:
        state = request(args.dashboard_url, "/api/state")
        now = time.monotonic() - start
        for board in board_ids:
            item = state["boards"][board]
            imu = item.get("imu", {})
            motor = item.get("motor", {})
            saw_running[board] = saw_running[board] or bool(motor.get("running"))
            accel = imu.get("accel", {})
            gyro = imu.get("gyro", {})
            samples.append({
                "t_s": now,
                "board": board,
                "connected": item.get("connected", False),
                "heading": imu.get("heading"),
                "roll": imu.get("roll"),
                "pitch": imu.get("pitch"),
                "accel_x": accel.get("x"),
                "accel_y": accel.get("y"),
                "accel_z": accel.get("z"),
                "gyro_x": gyro.get("x"),
                "gyro_y": gyro.get("y"),
                "gyro_z": gyro.get("z"),
                "temperature_c": imu.get("temperature_c"),
                "rpm": motor.get("rpm"),
                "target_rpm": motor.get("target_rpm"),
                "position_steps": motor.get("position_steps"),
                "target_steps": motor.get("target_steps"),
                "distance_rev": motor.get("distance_rev"),
                "mode": motor.get("mode"),
                "running": motor.get("running"),
            })
        if all(saw_running.values()) and all(
                not state["boards"][board]["motor"].get("running")
                for board in board_ids):
            completed = True
            break
        time.sleep(0.05)

    result = {
        "schema": 1,
        "dashboard_url": args.dashboard_url,
        "command": command,
        "boards": list(board_ids),
        "completed": completed,
        "elapsed_s": time.monotonic() - start,
        "sent_commands": sent,
        "samples": samples,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("saved", output)
    print("completed:", completed, "samples:", len(samples))
    return 0 if completed else 2


if __name__ == "__main__":
    raise SystemExit(main())
