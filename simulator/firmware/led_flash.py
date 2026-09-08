"""Minimal TinyPICO MicroPython LED smoke test.

This checks only the board, GPIO, and serial console. It does not enable the
TMC2209 or move the motor. TinyPICO's onboard indicator is an APA102/DotStar:
data GPIO2, clock GPIO12, and active-low LED power GPIO13.
"""

from machine import Pin
import time
try:
    import ujson as json
except ImportError:
    import json


LED_DATA = 2
LED_CLOCK = 12
LED_POWER = 13
FLASH_COUNT = 6
FLASH_MS = 250

data = Pin(LED_DATA, Pin.OUT, value=0)
clock = Pin(LED_CLOCK, Pin.OUT, value=0)
power = Pin(LED_POWER, Pin.OUT, value=1)


def write_byte(value):
    for bit in range(7, -1, -1):
        data.value((value >> bit) & 1)
        clock.value(1)
        clock.value(0)


def set_led(red, green, blue):
    power.value(0)  # TinyPICO LED power transistor is active-low.
    for _ in range(4):
        write_byte(0x00)  # APA102 start frame
    write_byte(0xE0 | 31)  # max global brightness
    write_byte(blue)
    write_byte(green)
    write_byte(red)
    for _ in range(4):
        write_byte(0xFF)  # APA102 end frame
    if red == 0 and green == 0 and blue == 0:
        power.value(1)


print(json.dumps({"type": "led_test", "state": "start", "led": "TinyPICO APA102", "data": LED_DATA, "clock": LED_CLOCK, "power": LED_POWER}))
for index in range(FLASH_COUNT):
    set_led(0, 24, 0)
    print(json.dumps({"type": "led_test", "state": "on", "count": index + 1}))
    time.sleep_ms(FLASH_MS)
    set_led(0, 0, 0)
    time.sleep_ms(FLASH_MS)

set_led(0, 0, 0)
print(json.dumps({"type": "led_test", "state": "done", "flashes": FLASH_COUNT}))
