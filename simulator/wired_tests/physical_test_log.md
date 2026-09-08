# First wired egg: physical control log

Session date: 2026-09-08

Board: `/dev/cu.usbserial-020D143B`  
Sensor: BNO055  
Stepper configuration: 200 full steps/rev, 16 microsteps, 3200 commanded steps/rev  
Firmware limits observed: 1–240 RPM, 1–120 RPM/s, 15,000 steps/s

All runs used the existing USB dashboard bridge. The runner sent a tare before
each motion case, sampled state at approximately 50 ms, and sent a stop in its
cleanup path. No firmware upload, reset, or erase occurred.

## Verified runs

| Case | Command | Result | IMU / thermal observation |
|---|---|---|---|
| Finite low speed | 3 RPM, 0.05 rev, + direction, 20 RPM/s | 160 steps reached; auto-stop; idle | Pitch peak 1.687°, gyro-vector peak 4.53 dps; 31 °C |
| One rock cycle | 4 RPM, 0.05 rev amplitude, 1 cycle, 20 RPM/s | Reversed at both amplitude boundaries; auto-stop | Pitch peak 3.062°, gyro-vector peak 13.73 dps; 31 °C |
| Sustain then stop | 8 RPM, 0.08 rev amplitude, continuous, 30 RPM/s | Explicit stop; idle | Stop latency 0.110 s; pitch peak 3.188°, gyro-vector peak 17.77 dps; 31 °C |
| Reverse while sustaining | 8 RPM continuous, then `set direction=-1` | Telemetry showed both directions; explicit stop; idle | Stop latency 0.113 s; gyro-vector peak 12.81 dps; 31–32 °C |
| Half intensity | Base 12 RPM / 0.10 rev amplitude, intensity 0.5, 2 cycles | Firmware reported intensity 0.5; auto-stop; idle | Pitch peak 0.688°, gyro-vector peak 9.14 dps; 31–32 °C |
| Full circle forward | 3 RPM, exactly 1.0 rev, + direction, 20 RPM/s | 3200 steps reached; elapsed about 20.25 s; idle | Heading peak 10.06°, roll peak 11.19°, pitch peak 75.63°; 31 °C |
| Full circle reverse | 3 RPM, exactly 1.0 rev, − direction, 20 RPM/s | −3200 steps reached; elapsed about 20.17 s; idle | Heading peak 25.88°, roll peak 2.38°, pitch peak 43.75°; 31 °C |

Detailed machine-readable logs:

- `physical_case_01_verified.json`
- `physical_case_02.json`
- `physical_case_03.json`
- `physical_reverse_sustain.json`
- `physical_half_intensity.json`
- `physical_full_circle_run.json`
- `physical_full_circle_reverse_verified.json`

## Interpretation

The motor command path, distance completion, direction reversal, finite
rocking, continuous rocking, half-intensity scaling, and explicit stop path all
responded. The measured stop latency is approximately 110–113 ms through the
USB dashboard path.

The BNO055 Euler angles change substantially during a full turn, especially
pitch. Those values describe the IMU’s installation orientation and may cross
Euler singularities; they are not direct XYZ coordinates. Use the relative
coordinate model in `coordinate_system.py` together with motor step phase.

The firmware reported idle and not e-stopped after the final run. These tests
do not establish a safe maximum for the attached mechanical load.
