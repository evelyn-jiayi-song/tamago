#!/usr/bin/env python3
"""Run the LED smoke test directly on a MicroPython ESP32 over USB serial.

This uses the regular MicroPython REPL, so it does not install or overwrite a
file on the board. It interrupts the currently running program, evaluates the
small test, prints its serial output, and leaves the board at the REPL prompt.
"""

from __future__ import annotations

import argparse
import time

import serial


DOTSTAR_SCRIPT = """from machine import Pin
import time
try:
    import ujson as json
except ImportError:
    import json
LED_DATA = {data}
LED_CLOCK = {clock}
LED_POWER = {power}
data = Pin(LED_DATA, Pin.OUT, value=0)
clock = Pin(LED_CLOCK, Pin.OUT, value=0)
power = Pin(LED_POWER, Pin.OUT, value=1)
def write_byte(value):
    for bit in range(7, -1, -1):
        data.value((value >> bit) & 1)
        clock.value(1)
        clock.value(0)
def set_led(red, green, blue):
    power.value(0)
    for _ in range(4): write_byte(0x00)
    write_byte(0xFF)
    write_byte(blue); write_byte(green); write_byte(red)
    for _ in range(4): write_byte(0xFF)
    if red == 0 and green == 0 and blue == 0: power.value(1)
print(json.dumps({{'type':'led_test','state':'start','led':'TinyPICO APA102'}}))
for index in range(6):
    set_led(0, 24, 0)
    print(json.dumps({{'type':'led_test','state':'on','count':index+1}}))
    time.sleep_ms(250)
    set_led(0, 0, 0)
    time.sleep_ms(250)
set_led(0, 0, 0)
print(json.dumps({{'type':'led_test','state':'done','flashes':6}}))
"""


def read_until(port, marker: bytes, timeout: float) -> bytes:
    end = time.monotonic() + timeout
    data = bytearray()
    while time.monotonic() < end:
        data.extend(port.read(max(1, port.in_waiting)))
        if marker in data:
            return bytes(data)
        time.sleep(0.02)
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description="Flash the TinyPICO onboard APA102 LED")
    parser.add_argument("--port", default="/dev/cu.usbserial-020D143B")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--data-pin", type=int, default=2)
    parser.add_argument("--clock-pin", type=int, default=12)
    parser.add_argument("--power-pin", type=int, default=13)
    args = parser.parse_args()

    code = DOTSTAR_SCRIPT.format(data=args.data_pin, clock=args.clock_pin, power=args.power_pin)
    with serial.Serial(args.port, args.baudrate, timeout=0.1,
                       write_timeout=1, dsrdtr=False, rtscts=False) as port:
        port.reset_input_buffer()
        # Stop a running main.py and wait for the friendly REPL prompt.
        port.write(b"\x03\x03\r\n")
        output = read_until(port, b">>>", 3)
        if b">>>" not in output:
            raise SystemExit(
                "No MicroPython REPL detected on {}. Received: {}".format(
                    args.port, output.decode("utf-8", errors="replace")[-300:]))

        port.write(("exec(" + repr(code) + ")\r\n").encode("utf-8"))
        output = read_until(port, b">>>", 8)
        text = output.decode("utf-8", errors="replace")
        print(text.strip())
        if '"state": "done"' not in text and "'state': 'done'" not in text:
            raise SystemExit("LED test did not report completion")
        print("LED smoke test passed: {} TinyPICO DotStar flashes".format(6))


if __name__ == "__main__":
    main()
