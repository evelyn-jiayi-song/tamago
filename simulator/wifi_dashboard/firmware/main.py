"""ESP32 MicroPython firmware for a BNO055 + TMC2209 + stepper motor.

Upload main.py and bno055.py to the ESP32.  The USB serial connection carries
newline-delimited JSON.  The companion dashboard sends commands and plots the
telemetry emitted by this file.

IMPORTANT: verify the GPIO numbers against your exact ESP32 Mini Pico board.
The defaults are common ESP32 GPIOs, not a guarantee for every Mini Pico
variant.  The TMC2209 must have its motor supply and current limit set before
running a connected motor.
"""

from machine import I2C, PWM, Pin
import socket
import time
import sys
try:
    import ujson as json
except ImportError:
    import json
try:
    import uselect as select
except ImportError:
    import select

# Prefer the maintained BNO055 package in /lib. The existing root-level
# bno055.py remains as a fallback and is not deleted.
if "/lib" not in sys.path:
    sys.path.insert(0, "/lib")
from bno055 import BNO055

try:
    from wifi_secrets import WIFI_SSID, WIFI_PASSWORD
except ImportError:
    WIFI_SSID = ""
    WIFI_PASSWORD = ""


# ----------------------------- wiring/config -----------------------------
I2C_SDA = 21
I2C_SCL = 22
BNO055_ADDRESS = 0x28  # Move COM3 high for 0x29.

TMC_STEP = 25
TMC_DIR = 26
TMC_EN = 27            # TMC2209 ENN is active-low.
DIR_INVERT = False
MOTOR_STEPS_PER_REV = 200
MICROSTEPS = 16        # Must match MS1/MS2 or UART configuration on the driver.

MIN_RPM = 1.0
MAX_RPM = 240.0             # Software ceiling; validate against the real load.
MIN_ACCEL_RPM_S = 1.0
MAX_ACCEL_RPM_S = 120.0     # Software ceiling; tune after current/load testing.
DEFAULT_ACCEL_RPM_S = 60.0
MAX_STEP_RATE = 15000.0
TELEMETRY_PERIOD_MS = 33       # ~30 Hz IMU stream over 115200-baud JSON serial.
STEP_HIGH_US = 3       # TMC2209 requires a valid high pulse; 3 us is conservative.
I2C_FREQ = 100000      # Conservative for BNO055 clock stretching.
WIFI_HTTP_PORT = 80
HEARTBEAT_TIMEOUT_MS = 750


def emit(payload):
    print(json.dumps(payload))


def connect_wifi():
    """Join the configured WLAN without preventing USB fallback operation."""
    if not WIFI_SSID:
        return None, "wifi_secrets.py is not configured"
    try:
        import network
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not sta.isconnected():
            sta.connect(WIFI_SSID, WIFI_PASSWORD)
            deadline = time.ticks_add(time.ticks_ms(), 15000)
            while not sta.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
                time.sleep_ms(250)
        if not sta.isconnected():
            return sta, "Wi-Fi connection timeout"
        return sta, ""
    except Exception as exc:
        return None, repr(exc)


class WiFiHTTP:
    """Small nonblocking HTTP API for telemetry, commands, and heartbeat."""

    def __init__(self, sta):
        self.sta = sta
        self.pending = []
        self.state = {}
        self.last_heartbeat_ms = 0
        self.error = ""
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("0.0.0.0", WIFI_HTTP_PORT))
        self.server.listen(1)
        self.server.setblocking(False)

    def update_state(self, state):
        self.state = state

    def take_commands(self):
        commands = self.pending
        self.pending = []
        return commands

    def _reply(self, client, payload, status="200 OK"):
        body = json.dumps(payload).encode("utf-8")
        header = ("HTTP/1.1 {}\r\nContent-Type: application/json\r\n"
                  "Access-Control-Allow-Origin: *\r\n"
                  "Cache-Control: no-store\r\nContent-Length: {}\r\n"
                  "Connection: close\r\n\r\n").format(status, len(body))
        client.send(header.encode("utf-8") + body)

    def service(self):
        try:
            client, _ = self.server.accept()
        except OSError:
            return
        try:
            client.settimeout(0.15)
            data = client.recv(4096)
            if not data:
                return
            header, separator, body = data.partition(b"\r\n\r\n")
            request_line = header.split(b"\r\n", 1)[0].decode().split()
            method, path = request_line[0], request_line[1]
            if method == "OPTIONS":
                self._reply(client, {"ok": True})
                return
            if method == "GET" and path == "/api/state":
                self._reply(client, self.state)
                return
            if method == "POST" and path in ("/api/command", "/api/heartbeat"):
                if path == "/api/heartbeat":
                    self.last_heartbeat_ms = time.ticks_ms()
                    self._reply(client, {"ok": True})
                    return
                length = 0
                for line in header.decode().split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        length = int(line.split(":", 1)[1].strip())
                while len(body) < length:
                    body += client.recv(length - len(body))
                command = json.loads(body[:length] or b"{}")
                self.last_heartbeat_ms = time.ticks_ms()
                self.pending.append(command)
                self._reply(client, {"ok": True, "queued": True})
                return
            self._reply(client, {"ok": False, "error": "not found"}, "404 Not Found")
        except Exception as exc:
            self.error = repr(exc)
            try:
                self._reply(client, {"ok": False, "error": self.error}, "400 Bad Request")
            except Exception:
                pass
        finally:
            client.close()


def read_imu(imu):
    """Read a complete sample with bounded retries for transient I2C timeouts."""
    last_error = None
    for _ in range(3):
        try:
            return _read_imu_once(imu)
        except OSError as exc:
            last_error = exc
            time.sleep_ms(3)
    raise last_error


def _read_imu_once(imu):
    """Read one sample using the maintained or fallback driver API."""
    if hasattr(imu, "read"):
        sample = imu.read()
        calibration = sample.get("calibration", 0)
        if isinstance(calibration, int):
            calibration = {
                "sys": (calibration >> 6) & 0x03,
                "gyro": (calibration >> 4) & 0x03,
                "accel": (calibration >> 2) & 0x03,
                "mag": calibration & 0x03,
            }
        heading = sample["heading"]
        roll = sample["roll"]
        pitch = sample["pitch"]
        accel = sample["accel"]
        gyro = sample["gyro"]
        temperature = sample["temperature_c"]
    else:
        heading, roll, pitch = imu.euler()
        ax, ay, az = imu.accel()
        gx, gy, gz = imu.gyro()
        accel = {"x": ax, "y": ay, "z": az}
        gyro = {"x": gx, "y": gy, "z": gz}
        temperature = imu.temperature()
        cal_sys, cal_gyro, cal_accel, cal_mag = imu.cal_status()
        calibration = {"sys": cal_sys, "gyro": cal_gyro,
                       "accel": cal_accel, "mag": cal_mag}
    return {
        "heading": round(heading, 3),
        "roll": round(roll, 3),
        "pitch": round(pitch, 3),
        "accel": {key: round(accel[key], 3) for key in ("x", "y", "z")},
        "gyro": {key: round(gyro[key], 3) for key in ("x", "y", "z")},
        "temperature_c": int(temperature),
        "calibration": calibration,
    }


class Stepper:
    def __init__(self):
        self.step_pin = Pin(TMC_STEP, Pin.OUT, value=0)
        self.dir_pin = Pin(TMC_DIR, Pin.OUT, value=0)
        self.en_pin = Pin(TMC_EN, Pin.OUT, value=1)
        self.running = False
        self.estopped = False
        self.direction = 1
        self.rpm = 0.0
        self.target_rpm = 0.0
        self.accel_rpm_s = DEFAULT_ACCEL_RPM_S
        self.target_steps = 0
        self.position_steps = 0
        self.position_float_steps = 0.0
        self.step_rate_hz = 0.0
        self.run_started_us = 0
        self.last_update_us = 0
        self.step_pwm = None
        self.mode = "idle"
        self.amplitude_steps = 0
        self.pattern_cycles = 0
        self.half_cycles = 0
        self.intensity = 1.0

    @property
    def steps_per_rev(self):
        return MOTOR_STEPS_PER_REV * MICROSTEPS

    def _set_direction(self, direction):
        self.direction = 1 if direction >= 0 else -1
        logical = self.direction < 0
        if DIR_INVERT:
            logical = not logical
        self.dir_pin.value(1 if logical else 0)

    def configure(self, rpm=None, revolutions=None, direction=None, accel=None):
        if rpm is not None:
            rpm = float(rpm)
            if rpm < 0 or rpm > MAX_RPM:
                raise ValueError("rpm must be between 0 and {}".format(MAX_RPM))
            if rpm > 0 and rpm * self.steps_per_rev / 60.0 > MAX_STEP_RATE:
                raise ValueError("rpm exceeds the configured step-rate limit")
            self.target_rpm = rpm
            if not self.running:
                self.rpm = rpm
        if accel is not None:
            accel = float(accel)
            if accel < MIN_ACCEL_RPM_S or accel > MAX_ACCEL_RPM_S:
                raise ValueError("accel must be between {} and {} RPM/s".format(
                    MIN_ACCEL_RPM_S, MAX_ACCEL_RPM_S))
            self.accel_rpm_s = accel
        if direction is not None:
            previous_direction = self.direction
            self._set_direction(float(direction))
            if self.running and self.direction != previous_direction:
                self._stop_step_pwm()
                time.sleep_ms(1)
                self._start_step_pwm()
        if revolutions is not None:
            revolutions = float(revolutions)
            if revolutions < 0:
                raise ValueError("distance must be zero or positive revolutions")
            self.target_steps = int(round(revolutions * self.steps_per_rev))

        self.step_rate_hz = self.rpm * self.steps_per_rev / 60.0 if self.rpm > 0 else 0.0

    def _begin_motion(self, mode):
        if self.estopped:
            raise ValueError("motor is latched in emergency stop; send clear_estop")
        if self.target_rpm <= 0:
            raise ValueError("set rpm above zero before start")
        self.mode = mode
        self.running = True
        self.rpm = MIN_RPM
        self.position_steps = 0
        self.position_float_steps = 0.0
        self.half_cycles = 0
        self.run_started_us = time.ticks_us()
        self.last_update_us = self.run_started_us
        self.en_pin.value(0)
        self._start_step_pwm()

    def _start_step_pwm(self):
        frequency = max(1, int(round(self.rpm * self.steps_per_rev / 60.0)))
        self.step_pwm = PWM(Pin(TMC_STEP), freq=frequency, duty_u16=32768)

    def _stop_step_pwm(self):
        if self.step_pwm is not None:
            self.step_pwm.deinit()
            self.step_pwm = None
        self.step_pin.value(0)

    def start(self):
        self._begin_motion("run")

    def start_rock(self, rpm, amplitude_rev, cycles=0, accel=None, intensity=1.0):
        self.configure(rpm=rpm, accel=accel)
        amplitude_rev = float(amplitude_rev)
        if amplitude_rev <= 0:
            raise ValueError("amplitude_rev must be greater than zero")
        cycles = int(cycles)
        if cycles < 0:
            raise ValueError("cycles must be zero or positive")
        self.amplitude_steps = int(round(amplitude_rev * self.steps_per_rev))
        self.pattern_cycles = cycles
        self.intensity = float(intensity)
        self._set_direction(1)
        self._begin_motion("rock")

    def stop(self, emergency=False):
        self.running = False
        self._stop_step_pwm()
        self.en_pin.value(1)
        self.rpm = 0.0
        self.target_rpm = 0.0
        self.mode = "idle"
        if emergency:
            self.estopped = True

    def clear_estop(self):
        self.estopped = False

    def update(self):
        if not self.running:
            return
        now_us = time.ticks_us()
        dt = time.ticks_diff(now_us, self.last_update_us) / 1000000.0
        self.last_update_us = now_us
        if dt < 0:
            dt = 0
        if dt > 0.25:
            dt = 0.25

        change = self.accel_rpm_s * dt
        if self.rpm < self.target_rpm:
            self.rpm = min(self.target_rpm, self.rpm + change)
        else:
            self.rpm = max(self.target_rpm, self.rpm - change)
        frequency = max(1, int(round(self.rpm * self.steps_per_rev / 60.0)))
        if self.step_pwm is not None and frequency != self.step_pwm.freq():
            self.step_pwm.freq(frequency)

        self.step_rate_hz = self.rpm * self.steps_per_rev / 60.0
        self.position_float_steps += self.direction * self.step_rate_hz * dt
        self.position_steps = int(self.position_float_steps)

        if self.mode == "run" and self.target_steps:
            if abs(self.position_float_steps) >= self.target_steps:
                self.position_steps = self.target_steps * self.direction
                self.stop()
        elif self.mode == "rock" and self.amplitude_steps:
            while abs(self.position_float_steps) >= self.amplitude_steps:
                overshoot = abs(self.position_float_steps) - self.amplitude_steps
                self.position_float_steps = self.direction * (self.amplitude_steps - overshoot)
                self.position_steps = int(self.position_float_steps)
                self.direction *= -1
                self._set_direction(self.direction)
                self.half_cycles += 1
                if self.pattern_cycles and self.half_cycles >= self.pattern_cycles * 2:
                    self.position_float_steps = self.direction * self.amplitude_steps
                    self.position_steps = int(self.position_float_steps)
                    self.stop()
                    break

    def status(self):
        return {
            "running": self.running,
            "estopped": self.estopped,
            "rpm": self.rpm,
            "target_rpm": self.target_rpm,
            "accel_rpm_s": self.accel_rpm_s,
            "mode": self.mode,
            "direction": self.direction,
            "position_steps": self.position_steps,
            "target_steps": self.target_steps,
            "distance_rev": abs(self.position_steps) / self.steps_per_rev,
            "steps_per_rev": self.steps_per_rev,
            "amplitude_rev": self.amplitude_steps / self.steps_per_rev,
            "cycles": self.pattern_cycles,
            "half_cycles": self.half_cycles,
            "intensity": self.intensity,
            "limits": {"min_rpm": MIN_RPM, "max_rpm": MAX_RPM,
                       "min_accel_rpm_s": MIN_ACCEL_RPM_S,
                       "max_accel_rpm_s": MAX_ACCEL_RPM_S,
                       "max_step_rate": MAX_STEP_RATE},
        }


def apply_command(command, motor, imu, imu_offset):
    """Apply one command from USB or Wi-Fi and return a JSON-safe response."""
    name = command.get("cmd", "")
    if name in ("set", "run"):
        motor.configure(command.get("rpm"),
                        command.get("distance_rev", command.get("revolutions")),
                        command.get("direction", 1), command.get("accel"))
        if name == "run":
            motor.start()
        return {"type": "ack", "cmd": name, "motor": motor.status()}
    if name in ("rock", "peer_rock"):
        intensity = float(command.get("intensity", 1.0))
        if name == "peer_rock":
            peer = command.get("peer_status", {})
            if isinstance(peer, dict):
                intensity = float(peer.get("intensity", intensity))
        intensity = max(0.0, min(1.0, intensity))
        rpm = float(command.get("rpm", 60.0)) * intensity
        amplitude_rev = float(command.get("amplitude_rev", 0.25)) * intensity
        motor.start_rock(rpm, amplitude_rev, command.get("cycles", 0),
                         command.get("accel"), intensity)
        return {"type": "ack", "cmd": name, "motor": motor.status()}
    if name == "start":
        motor.start()
        return {"type": "ack", "cmd": name, "motor": motor.status()}
    if name == "stop":
        motor.stop()
        return {"type": "ack", "cmd": name, "motor": motor.status()}
    if name == "estop":
        motor.stop(emergency=True)
        return {"type": "ack", "cmd": name, "motor": motor.status()}
    if name == "clear_estop":
        motor.clear_estop()
        return {"type": "ack", "cmd": name, "motor": motor.status()}
    if name == "tare":
        if imu is not None:
            sample = read_imu(imu)
            for key in imu_offset:
                imu_offset[key] = sample[key]
        return {"type": "ack", "cmd": name}
    if name == "status":
        return {"type": "status", "motor": motor.status()}
    raise ValueError("unknown command")


def main():
    time.sleep_ms(500)  # BNO055 startup time when main.py auto-runs.
    i2c = I2C(0, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)
    addresses = i2c.scan()
    address = BNO055_ADDRESS if BNO055_ADDRESS in addresses else None
    if address is None:
        for candidate in (0x28, 0x29):
            if candidate in addresses:
                address = candidate
                break
    sensor_found = address is not None
    if address is None:
        emit({"type": "error", "message": "BNO055 not found", "i2c_scan": addresses})
        imu = None
    else:
        try:
            imu = BNO055(i2c, address=address)
            emit({"type": "ready", "sensor": "BNO055", "i2c_address": address})
        except Exception as exc:
            imu = None
            sensor_found = False
            emit({"type": "error", "message": "BNO055 init failed: {}".format(exc)})

    motor = Stepper()
    wifi, wifi_error = connect_wifi()
    http = None
    wifi_ip = None
    if wifi is not None and wifi.isconnected():
        try:
            wifi_ip = wifi.ifconfig()[0]
            http = WiFiHTTP(wifi)
            emit({"type": "wifi", "connected": True, "ip": wifi_ip,
                  "api": "http://{}:{}/api/state".format(wifi_ip, WIFI_HTTP_PORT)})
        except Exception as exc:
            wifi_error = "Wi-Fi HTTP server failed: {}".format(exc)
    if http is None:
        emit({"type": "wifi_error", "message": wifi_error or "Wi-Fi unavailable"})

    poller = select.poll()
    poller.register(sys.stdin, select.POLLIN)
    imu_offset = {"heading": 0.0, "roll": 0.0, "pitch": 0.0}
    last_telemetry = time.ticks_ms()
    last_imu = {"heading": 0.0, "roll": 0.0, "pitch": 0.0,
                "accel": {"x": 0.0, "y": 0.0, "z": 0.0},
                "gyro": {"x": 0.0, "y": 0.0, "z": 0.0},
                "temperature_c": 0, "calibration": 0}

    while True:
        motor.update()

        if http is not None:
            http.service()
            for command in http.take_commands():
                try:
                    apply_command(command, motor, imu, imu_offset)
                except Exception as exc:
                    http.error = str(exc)

            heartbeat_ms = http.last_heartbeat_ms
            if (motor.running and heartbeat_ms and
                    time.ticks_diff(time.ticks_ms(), heartbeat_ms) > HEARTBEAT_TIMEOUT_MS):
                motor.stop()
                http.error = "heartbeat timeout: motor stopped safely"

        if poller.poll(0):
            line = sys.stdin.readline()
            if line:
                try:
                    command = json.loads(line)
                    emit(apply_command(command, motor, imu, imu_offset))
                except Exception as exc:
                    emit({"type": "error", "message": str(exc)})

        now = time.ticks_ms()
        if time.ticks_diff(now, last_telemetry) >= TELEMETRY_PERIOD_MS:
            last_telemetry = now
            if imu is not None:
                try:
                    sample = read_imu(imu)
                    for key in imu_offset:
                        sample[key] -= imu_offset[key]
                    last_imu = sample
                except Exception as exc:
                    emit({"type": "error", "message": "IMU read failed: {}".format(exc)})
            emit({"type": "telemetry", "t_ms": time.ticks_ms(),
                  "sensor": "BNO055" if sensor_found else None,
                  "sensor_found": sensor_found,
                  "imu": last_imu, "motor": motor.status()})

        if http is not None:
            age_ms = None
            if http.last_heartbeat_ms:
                age_ms = time.ticks_diff(time.ticks_ms(), http.last_heartbeat_ms)
            http.update_state({
                "connected": True,
                "ready": sensor_found,
                "sensor": "BNO055" if sensor_found else None,
                "sensor_found": sensor_found,
                "imu": last_imu,
                "motor": motor.status(),
                "wifi": {"connected": True, "ip": wifi_ip},
                "heartbeat": {"armed": motor.running, "age_ms": age_ms,
                               "timeout_ms": HEARTBEAT_TIMEOUT_MS},
                "last_error": http.error,
            })


main()
