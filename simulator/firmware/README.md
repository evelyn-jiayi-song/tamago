# ESP32 MicroPython firmware

## Wiring assumed by `main.py`

| Signal | ESP32 default | Device |
|---|---:|---|
| I²C SDA | GPIO 21 | BNO055 SDA |
| I²C SCL | GPIO 22 | BNO055 SCL |
| STEP | GPIO 25 | TMC2209 STEP |
| DIR | GPIO 26 | TMC2209 DIR |
| EN | GPIO 27 | TMC2209 ENN |
| Ground | GND | common ground |

The exact Mini Pico pinout may differ. Change the constants at the top of
`main.py` before uploading. Power the TMC2209 motor supply from an appropriate
external supply, not from the ESP32 3.3 V pin. Set the TMC2209 current limit
for the actual NEMA motor and use the correct motor coil pairs.

`MICROSTEPS = 16` must agree with the MS1/MS2 jumper setting or the TMC2209
UART configuration. `MOTOR_STEPS_PER_REV = 200` is the common 1.8° NEMA motor
value; change it for a 0.9° motor. The firmware rejects commands that exceed
the configured step-rate limit.

The STEP output uses ESP32 hardware PWM, so the motor pulse train continues
while the BNO055 is being read over I²C. This keeps motor motion independent
of the serial/IMU telemetry loop.

## Upload

Install MicroPython for the ESP32 board, then from the `simulator/` directory:

```bash
mpremote connect /dev/cu.usbserial-020D143B fs cp firmware/bno055.py :bno055.py
mpremote connect /dev/cu.usbserial-020D143B fs cp firmware/main.py :main.py
mpremote connect /dev/cu.usbserial-020D143B reset
```

On reset, the firmware emits JSON. A healthy BNO055 reports a `ready` message
and then `telemetry` messages. If the sensor is not found, run an I²C scanner
or check power, ground, SDA/SCL, and the address strap (0x28/0x29).

## Safety

Test with the motor unloaded and with the driver disabled first. Keep a way to
remove motor power. `estop` disables ENN in software, but it is not a
replacement for a physical power cut. Do not attach the final load until
direction, current, acceleration, and travel have been verified.

## Sensor note

This driver is specifically for the BNO055 register map. If the label is
actually BNO080/BNO085/BNO086, that family speaks SHTP rather than the BNO055
register protocol. Replace the sensor module with a BNO055-compatible board or
port a BNO08x MicroPython driver while preserving the `read()` dictionary shape.
