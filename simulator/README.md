# Wobble Egg Simulator Environment

A precision physics simulation environment for testing motor control methods on bottom-heavy egg-shaped systems.

## Features

- **CAD Import**: Load Fusion 360 exported models (STEP, URDF, OBJ formats)
- **Physics Engine**: PyBullet-based rigid-body dynamics with real-world friction and damping
- **Mass/CoM Configuration**: Import or manually specify center-of-mass and weight distributions
- **Motor Method Testing**: Test all 10 motor control architectures against standardized metrics
- **Precision Metrics**: Tilt angle error, settling time, overshoot, energy efficiency, oscillation damping
- **Agent Integration**: Coordinated testing with engine-mechanism-control and physical-egg-wobble agents

## Project Structure

```
simulator/
├── README.md                          # Simulator and hardware setup
├── requirements.txt                   # Python and dashboard dependencies
├── src/
│   ├── physics_engine.py              # Rigid-body dynamics
│   ├── egg_model.py                   # Egg geometry and mass properties
│   ├── motor_methods.py               # 10 motor control implementations
│   ├── metrics.py                     # Evaluation metrics
│   └── cad_importer.py                # STEP, STL, OBJ, URDF, and YAML import
├── experiments/
│   ├── baseline_tests.py              # Standard motor-method benchmark
│   ├── main.py                        # Experiment entry point
│   └── upload_main.py                 # Upload helper
├── dashboard/
│   ├── server.py                      # Local serial-to-web bridge
│   ├── index.html                     # Live control dashboard
│   └── run_*.py                       # Hardware commissioning tools
├── firmware/
│   ├── main.py                        # ESP32 MicroPython application
│   └── bno055.py                      # BNO055 driver fallback
└── docs/
   └── CAD_IMPORT_GUIDE.md            # Fusion 360 export guidance
```

## Quick Start

### 1. Install Dependencies

```bash
cd simulator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Simulator Benchmark

Run all ten motor methods, or select one method by its 1-based index:

```bash
python experiments/baseline_tests.py --duration 30 --target-angle 15
python experiments/baseline_tests.py --method 1 --duration 10 --target-angle 15
```

Results are written to `results/baseline_study.json` by default. Add `--gui`
when running a single method to open the PyBullet viewer.

### 3. Import a CAD Model

```python
from src.cad_importer import CADImporter
from src.egg_model import EggModel

# Load Fusion 360 exported model (STEP format)
geometry = CADImporter.import_file('path/to/fusion_export.step')

# Configure physical properties
egg = EggModel.from_dict({
   'name': 'my_egg',
   'geometry': geometry,
   'mass': 500,
   'center_of_mass': [0, 0, -25],
   'inertia_tensor': [[1e5, 0, 0], [0, 1e5, 0], [0, 0, 9e4]],
   }
)
```

For Fusion 360 export details, see [docs/CAD_IMPORT_GUIDE.md](docs/CAD_IMPORT_GUIDE.md).

### 4. Test a Motor Method

```python
from src.motor_methods import EccentricMassSpinner
from src.physics_engine import EggSimulator

# Initialize simulator
sim = EggSimulator(egg)

# Test Method 1: Eccentric Mass Spinning
motor = EccentricMassSpinner(rpm=500, mass_offset=30)  # mm
results = sim.run_test(motor, duration=10, target_angle=15)

# Evaluate performance
metrics = results.compute_metrics()
print(f"Tilt accuracy: {metrics['tilt_error']:.2f}°")
print(f"Settling time: {metrics['settling_time']:.2f} s")
print(f"Power consumed: {metrics['power_average']:.2f} W")
```

## ESP32 motor + IMU dashboard

The hardware control add-on lives in [`firmware/`](firmware/) and
[`dashboard/`](dashboard/). It targets an ESP32 running MicroPython, a
BNO055-compatible IMU, a TMC2209 in STEP/DIR mode, and a two-phase NEMA
stepper motor.

1. Confirm the GPIOs and motor current limit in `firmware/main.py` before
   connecting a load. The default I²C pins are SDA 21 / SCL 22; default motor
   pins are STEP 25 / DIR 26 / EN 27.
2. Copy `firmware/main.py` and `firmware/bno055.py` to the ESP32. For example,
   with `mpremote`:

   ```bash
   pip install mpremote
   mpremote connect /dev/cu.usbserial-020D143B fs cp firmware/bno055.py :bno055.py
   mpremote connect /dev/cu.usbserial-020D143B fs cp firmware/main.py :main.py
   ```

3. Install the host dependency and start the dashboard:

   ```bash
   pip install -r requirements.txt
   python dashboard/server.py --port /dev/cu.usbserial-020D143B
   ```

   Open <http://127.0.0.1:8080>.

Use `python dashboard/server.py --dry-run` to preview the dashboard without
energizing a motor. The firmware uses the dependency-free
[`micropython-bno055`](https://github.com/micropython-IMU/micropython-bno055)
driver, installed on the board with `mpremote mip install
github:micropython-IMU/micropython-bno055`. The driver uses standard I²C
register reads, BNO055 hardware fusion, and a conservative 100 kHz bus for
clock stretching. The serial protocol is newline-delimited JSON; it accepts
`run`, `stop`, `estop`, `clear_estop`, and `tare` commands and emits IMU and
motor telemetry about every 100 ms.

The part name “BNU088” is ambiguous. The included driver is for Bosch BNO055
(I²C address 0x28 or 0x29). A BNO080/BNO085/BNO086 board uses the SHTP protocol
and needs a BNO08x MicroPython driver in place of `bno055.py`; the dashboard
protocol can remain unchanged.

The firmware uses hardware PWM for TMC2209 STEP generation, allowing the motor
to move while BNO055 I²C reads and dashboard telemetry continue. A short
unloaded test can be run with:

```bash
python dashboard/run_motor_test.py --rpm 5 --distance 0.25
```

For an IMU mounted on the moving weight, the commissioning feedback tuner can
use relative pitch or roll to adjust direction and RPM. Start with a small
angle and no load:

```bash
python dashboard/run_imu_feedback.py --axis pitch --target-angle 8 \
  --rpm 20 --max-rpm 60 --accel 30 --duration 10
```

The tuner tares the IMU at rest and always sends `stop` on exit. Its RPM and
acceleration values are commissioning limits, not guaranteed mechanical
limits; validate them against the motor, driver current, gearing, weight, and
frame before increasing them.

### First-principles LED smoke test

Before testing the IMU or motor, verify the smallest possible path: USB serial
opens → MicroPython accepts a command → an ESP32 GPIO changes → serial output
returns. This test does not touch the TMC2209 or motor:

```bash
python dashboard/run_led_flash.py --port /dev/cu.usbserial-020D143B
```

The TinyPICO onboard APA102 indicator defaults to data GPIO2, clock GPIO12,
and power GPIO13. Override them with `--data-pin`, `--clock-pin`, and
`--power-pin` if your board revision differs. The test runs in RAM and does
not overwrite `main.py`.

## Physics Model

The simulator uses a rigid-body dynamics engine based on PyBullet, with first-principles modeling of:

- **Gravitational restoring torque**: $\tau_{gravity} = mg \cdot d_{CoM} \cdot \sin(\theta)$
- **Angular acceleration**: $\alpha = \frac{\tau_{net}}{I}$
- **Damping**: Velocity-dependent (Rayleigh damping)
- **Contact dynamics**: Rolling friction, slip, static/kinetic transitions
- **Motor actuation**: Force/torque inputs from motor methods

For detailed derivations, see [docs/PHYSICS_MODEL.md](docs/PHYSICS_MODEL.md).

## Success Metrics (TBD)

The test harness evaluates each motor method against:

1. **Control Precision** (Primary)
   - Tilt angle steady-state error (±tolerance)
   - Overshoot on step input
   - Oscillation damping ratio
   - Settling time to 2% band

2. **Energy Efficiency** (Primary)
   - Average power consumption (W)
   - Energy per cycle (J)
   - Work done per radian of tilt

3. **Robustness** (Secondary)
   - Disturbance rejection (step torque input)
   - Startup behavior and ringing
   - Frequency response (Bode plot)
   - Thermal stability over extended runtime

4. **Mechanical Viability** (Secondary)
   - Peak motor torque vs. actuator limits
   - Heat dissipation requirements
   - Component stress and fatigue

## Integration with Agents

### physical-egg-wobble Agent
Validates the physics model and geometry assumptions. Use this agent to:
- Define egg geometry from first principles
- Verify center-of-mass calculations
- Check equilibrium and restoring torque

### engine-mechanism-control Agent
Tests motor control strategies and feedback laws. Use this agent to:
- Tune PID gains for closed-loop methods
- Design feedforward paths for known motion profiles
- Optimize actuator scheduling

### (New) simulation-validation Agent
Orchestrates simulator runs and metric evaluation. Use this agent to:
- Design test scenarios (sweep parameters, disturbances)
- Analyze results and recommend optimizations
- Compare methods and identify trade-offs

## Adding a Motor Method

1. Subclass `MotorMethod` in `src/motor_methods.py`
2. Implement `update(tilt_angle, dt)` → returns force/torque vector
3. Add power model: `get_power_consumption()` → returns Watts
4. Register in test harness
5. Run validation test: `python tests/test_motor_methods.py`

See [docs/ADDING_MOTOR_METHODS.md](docs/ADDING_MOTOR_METHODS.md) for examples.

## Requirements

- **Python 3.10+**
- **PyBullet** (physics engine)
- **NumPy/SciPy** (numerical computation)
- **Trimesh** (CAD geometry processing)
- **PyYAML** (configuration)
- **Matplotlib** (plotting results)
- **(Optional)** Pybind11 + URDF support for advanced CAD import

## Contributing

To add new motor methods or improve the physics model:

1. Create a feature branch: `git checkout -b feature/my-motor-method`
2. Implement and test locally
3. Run full test suite: `python -m pytest tests/`
4. Validate metrics: `python experiments/baseline_tests.py --validate`
5. Submit PR with results

## References

- PyBullet documentation: https://docs.bullet-project.org/
- First-principles rigid-body dynamics: Kane & Levinson (1985)
- Control theory for self-righting systems: Bar-Cohen & Hafez (2009)
- Daruma doll physics: Choi et al. "Tumbler Toy Dynamics" (2014)

## License

MIT (Adjust as needed)

## Contact

For questions about the simulator, contact [your-email] or consult the physical-egg-wobble and engine-mechanism-control agents.
