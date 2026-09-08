"""Flash the ESP32 Mini Pico's onboard APA102-compatible RGB LED."""
from machine import Pin, SPI
import time


# ESP32 Mini Pico onboard RGB LED wiring.
RGB_POWER = Pin(13, Pin.OUT, value=0)
RGB_SPI = SPI(
    1,
    baudrate=1_000_000,
    polarity=0,
    phase=0,
    sck=Pin(12),
    mosi=Pin(2),
    miso=Pin(19),
)

START_FRAME = b"\x00\x00\x00\x00"
END_FRAME = b"\xff\xff\xff\xff"


def set_rgb(red, green, blue):
    RGB_SPI.write(START_FRAME + bytes((0xFF, blue, green, red)) + END_FRAME)


try:
    while True:
        set_rgb(0, 32, 255)
        print("LED on")
        time.sleep_ms(500)

        set_rgb(0, 0, 0)
        print("LED off")
        time.sleep_ms(500)
finally:
    set_rgb(0, 0, 0)