"""
Quick-start guide for using the wobble egg simulator.
"""

# WOBBLE EGG SIMULATOR - QUICK START GUIDE

## Installation (5 minutes)

```bash
cd simulator
pip install -r requirements.txt
```

## Basic Usage (10 minutes)

### 1. Run Baseline Test

```bash
python experiments/baseline_tests.py --duration 30
```

This tests all 10 motor methods and outputs a results JSON file.

### 2. Test One Method

```bash
python experiments/baseline_tests.py --method 1 --target-angle 15 --duration 30
```

Tests Method 1 (Eccentric Mass Spinning) at 15° target angle for 30 seconds.

### 3. Load Your CAD Model

```python
from src import EggSimulator, CADImporter, EggModel
from pathlib import Path

# Option A: Use Fusion 360 export
geometry = CADImporter.import_file('data/cad/my_egg.step')

# Option B: Use parametric definition
config = {
    'name': 'my_egg',
    'geometry': {
        'profile': 'ellipsoid',
        'semi_axes': [35, 35, 40],
        'contact_radius': 35,
        'surface_roughness': 0.1,
        'shell_thickness': 2
    },
    'mass': {
        'total': 500,
        'center_of_mass': [0, 0, -25],
        'inertia_tensor': [[105000, 0, 0], [0, 105000, 0], [0, 0, 90000]]
    }
}

egg = EggModel.from_dict(config)
```

### 4. Run Custom Test

```python
from src import EggSimulator, create_standard_egg, EccentricMassSpinner, MetricsCalculator
import numpy as np

# Create egg and simulator
egg = create_standard_egg(mass_g=500, com_offset_mm=25)
sim = EggSimulator(egg, gui=False)  # Set gui=True to visualize

# Create motor method
motor = EccentricMassSpinner(rpm=500)

# Run for 30 seconds
times, angles, rates, forces, torques, powers = [], [], [], [], [], []

for step in range(30000):  # 30 seconds at 1 kHz
    tilt_angle = sim.get_tilt_angle_degrees()
    force, torque = motor.update(np.radians(tilt_angle), 0.001)
    
    sim.step(motor_force=force, motor_torque=torque)
    sim.record_power(motor.get_power_consumption())
    
    # Record data
    times.append(sim.get_time())
    angles.append(tilt_angle)
    rates.append(sim.get_tilt_rate())
    forces.append(force)
    torques.append(torque)
    powers.append(motor.get_power_consumption())

# Evaluate
calculator = MetricsCalculator(target_angle_deg=15.0)
result = calculator.evaluate(
    method_name=motor.name,
    times=np.array(times),
    tilt_angles_deg=np.array(angles),
    tilt_rates=np.array(rates),
    motor_forces=np.array(forces),
    motor_torques=np.array(torques),
    power_samples=np.array(powers)
)

print(result.summary())
```

## Motor Methods (10 Available)

1. **Eccentric Mass Spinning** (2–5 W)
   - Simple rotating mass
   - Best for low power

2. **Linear Solenoid Slider** (5–15 W)
   - Electromagnetic pusher
   - Good for feedback control

3. **Electroactive Polymer (EAP)** (1–3 W)
   - Material-based actuator
   - Very efficient but slow

4. **Hydraulic Piston** (8–20 W)
   - Fluid-driven
   - High force

5. **Voice Coil Motor** (3–8 W)
   - Linear motor
   - Smooth response

6. **Reactive Pendulum** (2–6 W)
   - Swinging arm
   - Very stable

7. **Piezoelectric Stack** (0.5–2 W)
   - High-voltage piezo
   - Highly efficient

8. **Shape-Memory Alloy (SMA)** (5–15 W)
   - Thermal cycling
   - Silent

9. **BLDC Cam Follower** (3–8 W)
   - High-speed motor + cam
   - Proven technology

10. **Adaptive Resonance Tracker** (1–3 W)
    - Frequency-tracking control
    - Energy optimal

## Success Metrics

Each method is evaluated on:

- **Control Precision** (40% weight)
  - Steady-state error (goal: < 2°)
  - Overshoot (goal: < 10%)
  - Settling time (goal: < 2s)

- **Energy Efficiency** (30% weight)
  - Average power (lower is better)
  - Energy per cycle
  - Power rating (0-100 scale)

- **Robustness** (20% weight)
  - Step response time
  - Damping ratio
  - Bandwidth

- **Mechanical Viability** (10% weight)
  - Peak torque vs. actuator limit
  - Peak force vs. actuator limit
  - Thermal load

Overall Score: 0-100 (higher is better)

## Project Structure

```
simulator/
├── README.md                 # Full documentation
├── requirements.txt          # Python dependencies
├── config/                   # Configuration files
│   ├── simulation_config.yaml
│   └── egg_models/          # Egg model definitions
├── src/                      # Core simulator
│   ├── physics_engine.py     # PyBullet wrapper
│   ├── egg_model.py          # Egg body definition
│   ├── motor_methods.py      # 10 control methods
│   ├── metrics.py            # Evaluation metrics
│   └── cad_importer.py       # CAD file loading
├── tests/                    # Unit tests
├── experiments/              # Test scripts
│   └── baseline_tests.py    # Main test runner
├── data/cad/                # CAD models (your Fusion exports)
├── results/                 # Output data and plots
└── docs/                    # Documentation
    ├── CAD_IMPORT_GUIDE.md  # How to export from Fusion 360
    ├── PHYSICS_MODEL.md     # First-principles derivations
    └── ADDING_MOTOR_METHODS.md  # How to add new methods
```

## Common Tasks

### Export from Fusion 360

See [docs/CAD_IMPORT_GUIDE.md](docs/CAD_IMPORT_GUIDE.md) for detailed instructions.

Quick steps:
1. In Fusion → Right-click body → Save as Mesh
2. Choose STEP format
3. Save to `data/cad/my_egg.step`
4. Create `config/egg_models/my_egg.yaml` with mass properties
5. Run simulation

### Add New Motor Method

1. Subclass `MotorMethod` in `src/motor_methods.py`
2. Implement `update(angle, dt)` and `get_power_consumption()`
3. Add to `create_all_methods()` factory function
4. Test: `python experiments/baseline_tests.py`

### Visualize Results

```python
import json
import matplotlib.pyplot as plt

# Load results
with open('results/baseline_study.json') as f:
    data = json.load(f)

# Extract method rankings
methods = [r['method_name'] for r in data['results']]
scores = [r['overall_score'] for r in data['results']]
powers = [r['energy']['average_power'] for r in data['results']]

# Plot
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

ax1.bar(range(len(methods)), scores)
ax1.set_ylabel('Overall Score (0-100)')
ax1.set_xticks(range(len(methods)))
ax1.set_xticklabels(methods, rotation=45, ha='right')
ax1.set_title('Motor Method Rankings')
ax1.grid(axis='y', alpha=0.3)

ax2.bar(range(len(methods)), powers)
ax2.set_ylabel('Average Power (Watts)')
ax2.set_xticks(range(len(methods)))
ax2.set_xticklabels(methods, rotation=45, ha='right')
ax2.set_title('Power Consumption')
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.show()
```

## Debugging

### Simulation Won't Start
```
ImportError: No module named 'pybullet'
→ Run: pip install -r requirements.txt
```

### CAD File Not Loading
```
FileNotFoundError: CAD file not found
→ Check file path (use relative paths from simulator root)
→ Supported formats: .step, .stl, .obj, .urdf, .yaml
```

### Physics Seems Wrong
1. Verify egg mass in Fusion 360 matches config file
2. Check center-of-mass location (must be negative Z = below center)
3. Run with `gui=True` to visualize: `EggSimulator(egg, gui=True)`
4. See [docs/PHYSICS_MODEL.md](docs/PHYSICS_MODEL.md) for first-principles validation

### Metrics Don't Look Right
1. Check target angle: should match your test scenario
2. Verify settling band: default ±2° may be too tight for some methods
3. Review metric definitions in `src/metrics.py`
4. Compare to baseline (standard 500g egg)

## Agent Integration

Use the specialized agents for guidance:

### simulation-validation Agent
- Designs comprehensive test scenarios
- Interprets metrics and identifies trade-offs
- Recommends design optimizations
- Compares methods on Pareto frontier

### engine-mechanism-control Agent
- Tunes control laws (PID gains, feedforward)
- Interprets actuator dynamics
- Optimizes control parameters

### physical-egg-wobble Agent
- Validates physics model
- Derives first-principles equations
- Checks mass/CoM assumptions

## References

- **Simulator:** PyBullet documentation https://docs.bullet-project.org/
- **Physics:** Kane & Levinson (1985), *Dynamics: Theory and Applications*
- **Control:** Kuo & Golnaraghi (2017), *Automatic Control Systems*
- **CAD:** Fusion 360 tutorials https://help.autodesk.com/view/fusion360/ENU/

---

**Ready to run tests? Start with:**
```bash
python experiments/baseline_tests.py --duration 30 --target-angle 15
```

For questions, consult the detailed README.md or docs/ directory.
