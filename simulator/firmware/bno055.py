"""Small BNO055 I2C driver for MicroPython.

The driver reads the BNO055 fused Euler angles plus raw accelerometer and
gyroscope values.  It deliberately has no third-party dependencies so it can
be copied to an ESP32 together with main.py.
"""

import time

try:
    _sleep_ms = time.sleep_ms
except AttributeError:  # lets the register math be unit-tested on a laptop
    def _sleep_ms(milliseconds):
        time.sleep(milliseconds / 1000.0)


class BNO055:
    CHIP_ID = 0xA0
    ADDRESS_PRIMARY = 0x29
    ADDRESS_ALTERNATE = 0x28

    REG_CHIP_ID = 0x00
    REG_PAGE_ID = 0x07
    REG_ACC_DATA = 0x08
    REG_EULER_DATA = 0x1A
    REG_TEMP = 0x34
    REG_CALIB_STAT = 0x35
    REG_OPR_MODE = 0x3D
    REG_PWR_MODE = 0x3E
    REG_SYS_TRIGGER = 0x3F
    REG_UNIT_SEL = 0x3B
    CONFIG_MODE = 0x00
    IMU_MODE = 0x08
    NDOF_MODE = 0x0C

    def __init__(self, i2c, address=ADDRESS_PRIMARY, mode=NDOF_MODE):
        self.i2c = i2c
        self.address = address
        self.mode = mode
        self._begin()

    def _write8(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value & 0xFF,)))

    def _read(self, register, length):
        return self.i2c.readfrom_mem(self.address, register, length)

    def _begin(self):
        chip_id = self._read(self.REG_CHIP_ID, 1)[0]
        if chip_id != self.CHIP_ID:
            raise OSError("BNO055 not found (chip id 0x{:02x})".format(chip_id))

        self._write8(self.REG_OPR_MODE, self.CONFIG_MODE)
        _sleep_ms(25)
        self._write8(self.REG_PAGE_ID, 0)
        self._write8(self.REG_PWR_MODE, 0x00)
        self._write8(self.REG_SYS_TRIGGER, 0x00)
        # 0x00: Celsius, m/s^2, dps, degrees, Android orientation.
        self._write8(self.REG_UNIT_SEL, 0x00)
        _sleep_ms(10)
        self._write8(self.REG_OPR_MODE, self.mode)
        _sleep_ms(20)

    @staticmethod
    def _s16(data, index):
        value = data[index] | (data[index + 1] << 8)
        return value - 65536 if value & 0x8000 else value

    def read(self):
        # 0x08..0x1f contains accel, mag, gyro, and Euler registers.
        data = self._read(self.REG_ACC_DATA, 24)
        accel = tuple(self._s16(data, i) / 100.0 for i in (0, 2, 4))
        gyro = tuple(self._s16(data, i) / 16.0 for i in (12, 14, 16))
        euler = tuple(self._s16(data, i) / 16.0 for i in (18, 20, 22))
        return {
            "heading": euler[0],
            "roll": euler[1],
            "pitch": euler[2],
            "accel": {"x": accel[0], "y": accel[1], "z": accel[2]},
            "gyro": {"x": gyro[0], "y": gyro[1], "z": gyro[2]},
            "temperature_c": (lambda raw: raw - 256 if raw & 0x80 else raw)(self._read(self.REG_TEMP, 1)[0]),
            "calibration": self._read(self.REG_CALIB_STAT, 1)[0],
        }
