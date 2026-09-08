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
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── setup.py                          # Package configuration
├── config/
│   ├── simulation_config.yaml         # Global physics parameters
│   └── egg_models/                    # CAD model definitions
│       └── sample_egg.yaml            # Example: mass, CoM, geometry
├── src/
│   ├── __init__.py
│   ├── physics_engine.py              # PyBullet wrapper & dynamics
│   ├── cad_importer.py                # CAD file handling (STEP, URDF, OBJ)
│   ├── egg_model.py                   # Egg body with configurable mass/CoM
│   ├── motor_methods.py               # 10 motor control implementations
│   ├── test_harness.py                # Test runner for all methods
│   ├── metrics.py                     # Success metric calculators
│   └── visualization.py               # Real-time 3D visualization (optional)
├── tests/
│   ├── __init__.py
│   ├── test_cad_import.py             # CAD loading validation
│   ├── test_physics_engine.py         # Dynamics verification
│   ├── test_motor_methods.py          # Individual method tests
│   └── test_metrics.py                # Metric computation validation
├── experiments/
│   ├── baseline_tests.py              # Standard test suite
│   ├── frequency_sweep.py             # Resonance characterization
│   ├── energy_efficiency_test.py      # Power consumption analysis
│   └── results/                       # Output data and plots
└── docs/
    ├── PHYSICS_MODEL.md               # First-principles dynamics
    ├── CAD_IMPORT_GUIDE.md            # How to export from Fusion 360
    └── ADDING_MOTOR_METHODS.md        # Extension guide for new methods
```

## Quick Start

### 1. Install Dependencies

```bash
cd simulator
pip install -r requirements.txt
```

### 2. Import a CAD Model

```python
from src.cad_importer import import_cad
from src.egg_model import EggModel

# Load Fusion 360 exported model (STEP format)
geometry = import_cad('path/to/fusion_export.step')

# Configure physical properties
egg = EggModel(
    geometry=geometry,
    mass=500,  # grams
    center_of_mass=(0, 0, -25),  # mm, relative to geometric center
    inertia_tensor=[[1e5, 0, 0], [0, 1e5, 0], [0, 0, 9e4]]  # g·mm²
)
```

### 3. Test a Motor Method

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

### 4. Run Full Benchmark

```bash
python experiments/baseline_tests.py \
    --model config/egg_models/sample_egg.yaml \
    --output results/benchmark_2026_08_18.json
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
