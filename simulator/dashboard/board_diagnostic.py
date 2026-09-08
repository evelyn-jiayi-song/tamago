#!/usr/bin/env python3
"""Safe console diagnostics for one or more ESP32 MicroPython boards.

Examples:
    python3 dashboard/board_diagnostic.py --port /dev/cu.usbserial-020D15CD
    python3 dashboard/board_diagnostic.py \
        --port /dev/cu.usbserial-020D143B \
        --port /dev/cu.usbserial-020D15CD

The check uses MicroPython's raw REPL to inspect the board. It does not erase,
upload, or change files. A normal reset is sent afterward so an existing
main.py can resume. Stop the USB dashboard bridge before testing a port that it
currently owns.
"""

from __future__ import annotations

import argparse
import glob
import subprocess
import sys
from pathlib import Path


CHECK = r"""
import machine, network, os, sys

print('MICROPYTHON_OK')
print('UNAME', os.uname())
try:
    sta = network.WLAN(network.STA_IF)
    print('MAC', ':'.join('{:02X}'.format(x) for x in sta.config('mac')))
except Exception as exc:
    print('MAC_ERROR', repr(exc))

try:
    i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=100000)
    addresses = i2c.scan()
    print('I2C_SCAN', addresses)
    found = False
    for address in (0x28, 0x29):
        if address in addresses:
            try:
                chip_id = i2c.readfrom_mem(address, 0x00, 1)[0]
                print('BNO055', hex(address), 'CHIP_ID', hex(chip_id))
                found = True
            except Exception as exc:
                print('BNO055_READ_ERROR', hex(address), repr(exc))
    if not found:
        print('BNO055_NOT_FOUND')
except Exception as exc:
    print('I2C_ERROR', repr(exc))

try:
    import bno055
    print('BNO055_DRIVER_OK')
except Exception as exc:
    print('BNO055_DRIVER_ERROR', repr(exc))

try:
    import espnow
    print('ESPNOW_OK')
except Exception as exc:
    print('ESPNOW_ERROR', repr(exc))
"""


def run_mpremote(port: str, *commands: str) -> tuple[int, str]:
    """Run mpremote using the current Python environment."""
    command = [sys.executable, "-m", "mpremote", "connect", port]
    for item in commands:
        command.extend(item.split("\0"))
    result = subprocess.run(command, text=True, capture_output=True)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def diagnose(port: str) -> bool:
    print("\n=== {} ===".format(port))
    print("Read-only check: no erase, no upload")
    code, output = run_mpremote(port, "exec\0" + CHECK)
    if output:
        print(output.rstrip())
    if code != 0:
        print("RESULT FAIL: could not complete MicroPython diagnostic (exit {})".format(code))
        return False

    required = {
        "MICROPYTHON_OK": "MicroPython",
        "BNO055_DRIVER_OK": "bno055.py driver",
        "ESPNOW_OK": "ESP-NOW module",
    }
    missing = [label for marker, label in required.items() if marker not in output]
    if not any(marker in output for marker in ("BNO055 0x28", "BNO055 0x29")):
        missing.append("BNO055 hardware")
    if missing:
        print("RESULT FAIL: missing or unavailable: {}".format(", ".join(missing)))
        reset_code, reset_output = run_mpremote(port, "reset")
        if reset_output.strip():
            print("reset:", reset_output.strip())
        if reset_code != 0:
            print("RESULT WARN: diagnostic failed and normal reset failed")
        return False

    reset_code, reset_output = run_mpremote(port, "reset")
    if reset_output.strip():
        print("reset:", reset_output.strip())
    if reset_code != 0:
        print("RESULT WARN: diagnostic passed but normal reset failed")
        return False
    print("RESULT PASS: board diagnostic complete; existing main.py may resume")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        action="append",
        dest="ports",
        help="serial port; repeat for multiple boards",
    )
    parser.add_argument(
        "--all-usbserial",
        action="store_true",
        help="test all /dev/cu.usbserial-* devices",
    )
    args = parser.parse_args()

    ports = list(args.ports or [])
    if args.all_usbserial:
        ports.extend(glob.glob("/dev/cu.usbserial-*")
                     or glob.glob("/dev/tty.usbserial-*"))
    ports = list(dict.fromkeys(ports))
    if not ports:
        parser.error("provide --port or use --all-usbserial")

    results = [diagnose(port) for port in ports]
    print("\nSUMMARY: {}/{} boards passed".format(sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
