# Default starting position: balanced and still

The current physical pose is the system’s mechanical reference position:

> The egg is completely balanced and still, with the moving weight at rest.

This is named `balanced_still`.  In this coordinate system it is always:

```text
shaft_deg = 0
shaft_rev = 0
heading_deg = 0
roll_deg = 0
pitch_deg = 0
tilt_magnitude_deg = 0
```

The BNO055 does not measure absolute XYZ position.  The system therefore
records the motor shaft phase from TMC2209 step counts and records the BNO055
orientation relative to this reference.  If the arm radius is supplied, the
shaft phase is also converted to an estimated XY point in the mechanism plane.

## Live reference observation

Captured from the working USB dashboard while the motor was idle:

```json
{
  "reference": "balanced_still",
  "position_steps": 0,
  "heading_deg_raw": 238.125,
  "roll_deg_raw": -85.688,
  "pitch_deg_raw": -2.375,
  "gyro_dps": {"x": -0.188, "y": 0.062, "z": 0.062},
  "temperature_c": 32,
  "motor_running": false
}
```

The raw Euler values are installation-dependent and are not treated as global
compass/level coordinates.  The relative values above are the control values.
At startup or after physically repositioning the egg, capture a new reference
only while it is balanced and motionless; do not tare while the motor is moving.
