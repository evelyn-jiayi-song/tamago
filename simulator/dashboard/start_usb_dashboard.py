#!/usr/bin/env python3
"""Start the two-egg USB dashboard using currently visible serial devices."""

from __future__ import annotations

import argparse
import glob
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-port", type=int, default=8090)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--peer-mode", action="store_true")
    args = parser.parse_args()
    ports = sorted(glob.glob("/dev/cu.usbserial-*") +
                   glob.glob("/dev/cu.usbmodem-*"))
    if not ports:
        raise SystemExit("No ESP32 USB serial devices found")
    if len(ports) > 2:
        ports = ports[:2]
    command = [
        sys.executable, "dashboard/server.py", "--http-port",
        str(args.http_port), "--baudrate", str(args.baudrate),
    ]
    for port in ports:
        command.extend(["--port", port])
    if args.peer_mode:
        command.append("--peer-mode")
    print("Starting dashboard for:", ", ".join(ports))
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
