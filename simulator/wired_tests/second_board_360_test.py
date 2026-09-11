"""Run one low-speed 360-degree turn on the second ESP32 board.

This is a temporary MicroPython script for ``mpremote run``. It does not
erase or install firmware. It assumes the TMC2209 is configured for 16x
microstepping: 200 full steps/rev * 16 = 3200 STEP pulses/rev.

Verify that the mechanism is clear, the motor supply is current-limited, and
the board is idle before running this test. The driver is disabled in the
``finally`` block even if the test is interrupted.
"""

from machine import Pin
import time


STEP = Pin(25, Pin.OUT, value=0)
DIR = Pin(26, Pin.OUT, value=0)
ENABLE = Pin(27, Pin.OUT, value=1)

STEPS = 3200
STEP_PERIOD_US = 5000  # about 3.75 RPM at 3200 pulses/rev
DIR_VALUE = 0


def move_one_revolution():
    ENABLE.value(0)
    DIR.value(DIR_VALUE)
    for _ in range(STEPS):
        STEP.value(1)
        time.sleep_us(3)
        STEP.value(0)
        time.sleep_us(STEP_PERIOD_US - 3)


try:
    print("SECOND_MOTOR_360_START steps={}".format(STEPS))
    move_one_revolution()
    print("SECOND_MOTOR_360_COMPLETE steps={}".format(STEPS))
finally:
    STEP.value(0)
    ENABLE.value(1)
    print("SECOND_MOTOR_360_DISABLED")
