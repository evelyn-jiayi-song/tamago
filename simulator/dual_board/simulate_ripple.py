#!/usr/bin/env python3
"""Dry-run the two-board ripple protocol with synthetic IMU samples.

This script only evaluates dictionaries in memory. It does not open a serial
port, import ``machine``, use ESP-NOW, or issue motor commands.
"""

import argparse
import math
import os
import sys

try:
    from simulator.dual_board.ripple_logic import FollowerController, ReferencePublisher
except ImportError:  # Direct invocation: python3 simulator/dual_board/simulate_ripple.py
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ripple_logic import FollowerController, ReferencePublisher


def simulated_imu(time_s):
    """Still -> moving -> still synthetic BNO055-shaped data."""
    moving = 0.5 <= time_s < 3.0
    gyro_z = (45.0 + 15.0 * math.sin(time_s * 8.0)) if moving else 0.0
    dynamic = (0.5 * math.sin(time_s * 8.0)) if moving else 0.0
    return {
        "gyro": {"x": 0.0, "y": 0.0, "z": gyro_z},
        "accel": {"x": 0.0, "y": 0.0, "z": 9.80665 + dynamic},
    }


def run(duration_s, step_ms, drop_after_ms=None, delay_ms=250, target_fraction=0.5):
    publisher = ReferencePublisher(source="A", publish_period_ms=step_ms)
    follower = FollowerController(source="A", delay_ms=delay_ms,
                                  target_fraction=target_fraction)
    packet_count = 0
    command_count = {"rock": 0, "stop": 0}
    first_motion_tx = None
    first_motion_command = None

    for now_ms in range(0, int(duration_s * 1000) + 1, step_ms):
        packet = publisher.update(simulated_imu(now_ms / 1000.0), now_ms)
        if packet is not None:
            if first_motion_tx is None and packet["kind"] == "motion":
                first_motion_tx = now_ms
            if drop_after_ms is None or now_ms < drop_after_ms:
                follower.receive(packet, now_ms)
                packet_count += 1
                print("A -> B  t={:5.2f}s  kind={:<6} seq={:3d} intensity={:.3f}".format(
                    now_ms / 1000.0, packet["kind"], packet["seq"], packet["intensity"]))
        command = follower.tick(now_ms)
        if command is not None:
            command_count[command["cmd"]] += 1
            if first_motion_command is None and command["cmd"] == "rock":
                first_motion_command = now_ms
            print("B intent t={:5.2f}s  {}".format(now_ms / 1000.0, command))

    print("\nSummary")
    print("  packets accepted: {}".format(packet_count))
    print("  rock intents: {}".format(command_count["rock"]))
    print("  stop intents: {}".format(command_count["stop"]))
    if first_motion_tx is not None and first_motion_command is not None:
        print("  observed ripple delay: {} ms".format(first_motion_command - first_motion_tx))
    if drop_after_ms is not None:
        print("  packet delivery stopped at: {} ms (stale-stop path)".format(drop_after_ms))


def main():
    parser = argparse.ArgumentParser(description="Dry-run the isolated ESP-NOW ripple logic")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--step-ms", type=int, default=50)
    parser.add_argument("--drop-after-ms", type=int, default=None,
                        help="stop delivering packets to exercise stale timeout")
    parser.add_argument("--delay-ms", type=int, default=250)
    parser.add_argument("--target-fraction", type=float, default=0.5)
    args = parser.parse_args()
    if args.duration <= 0 or args.step_ms <= 0:
        parser.error("duration and step-ms must be positive")
    run(args.duration, args.step_ms, args.drop_after_ms,
        args.delay_ms, args.target_fraction)


if __name__ == "__main__":
    main()
