#!/usr/bin/env python3
"""Upload a MicroPython program as ``main.py`` and run it on the ESP32."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import serial


def read_for(port, seconds):
    end = time.monotonic() + seconds
    data = bytearray()
    while time.monotonic() < end:
        chunk = port.read(4096)
        if chunk:
            data.extend(chunk)
        else:
            time.sleep(0.01)
    return bytes(data)


def read_until(port, marker, timeout):
    end = time.monotonic() + timeout
    data = bytearray()
    while time.monotonic() < end:
        chunk = port.read(4096)
        if chunk:
            data.extend(chunk)
            if marker in data:
                return bytes(data)
        else:
            time.sleep(0.01)
    raise TimeoutError(
        f"timed out waiting for {marker!r}; received {bytes(data)!r}"
    )


def upload(port, source):
    time.sleep(0.5)
    port.reset_input_buffer()
    port.write(b"\x03\x03")
    time.sleep(0.2)
    port.write(b"\x01")
    raw_repl = read_until(port, b"raw REPL", 3)

    command = "f=open('main.py','w');f.write(" + repr(source) + ");f.close()"
    port.write(command.encode("utf-8") + b"\x04")
    result = read_until(port, b"\x04", 5)
    if b"Traceback" in result or b"Error" in result:
        sys.stderr.buffer.write(result)
        raise RuntimeError("MicroPython rejected the file upload")

    port.write(b"\x02")
    time.sleep(0.2)
    port.write(b"import machine; machine.reset()\r\n")
    output = read_for(port, 3)
    return raw_repl + result + output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="serial device, for example /dev/cu.usbserial-020D143B")
    parser.add_argument("source", type=Path, help="local MicroPython file to upload")
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"source file does not exist: {args.source}")

    source = args.source.read_text(encoding="utf-8")
    try:
        with serial.Serial(args.port, 115200, timeout=0.1) as port:
            output = upload(port, source)
    except serial.SerialException as exc:
        raise SystemExit(f"could not open {args.port}: {exc}") from exc

    sys.stdout.buffer.write(output)
    if b"LED on" not in output or b"LED off" not in output:
        raise RuntimeError("ESP32 reset completed, but the payload produced no LED output")


if __name__ == "__main__":
    main()