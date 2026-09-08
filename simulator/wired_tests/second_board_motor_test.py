"""Non-persistent second-board motor connection test.

Run with mpremote ``run``. This is intentionally not copied to the board.
It emits 160 STEP pulses (a small 0.05 revolution at 3200 steps/rev), then
disables the TMC2209. Confirm the motor is mechanically clear first.
"""

from machine import Pin
import time


STEP = Pin(25, Pin.OUT, value=0)
DIR = Pin(26, Pin.OUT, value=0)
ENABLE = Pin(27, Pin.OUT, value=1)
STEPS = 160
STEP_PERIOD_US = 5000


def move(steps):
    ENABLE.value(0)
    DIR.value(0)
    for _ in range(steps):
        STEP.value(1)
        time.sleep_us(3)
        STEP.value(0)
        time.sleep_us(STEP_PERIOD_US - 3)
    ENABLE.value(1)


try:
    print("SECOND_MOTOR_TEST_START steps={}".format(STEPS))
    move(STEPS)
    print("SECOND_MOTOR_TEST_COMPLETE steps={}".format(STEPS))
finally:
    STEP.value(0)
    ENABLE.value(1)
    print("SECOND_MOTOR_TEST_DISABLED")
