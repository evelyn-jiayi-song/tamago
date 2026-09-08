# Fusion 360 CAD Import Guide

This guide explains how to export your egg-shaped design from Fusion 360 and import it into the simulator.

## Step 1: Prepare Your Fusion 360 Design

1. Open your egg body in Fusion 360
2. Ensure the design is fully parametric with:
   - Correct mass properties (use Fusion 360's mass analysis)
   - Accurate geometry (shell thickness, internal structure)
   - Clear center of mass location

### Getting Mass Properties in Fusion 360

1. **Calculate mass:**
   - Design → Inspect → Mass Properties
   - Record total mass (grams)
   - Record center of mass coordinates (mm from geometric center)
   - Record inertia tensor (g·mm²)

2. **Save these values** for configuration file

## Step 2: Export Geometry

### Option A: STEP Format (Recommended)

1. Right-click body in Design Tree → **Save as Mesh**
2. Choose file format: **STEP (.step)**
3. Save to: `simulator/data/cad/my_egg.step`
4. Note: Mesh exports from solids are most accurate

### Option B: STL Format

1. Right-click body → **Save as Mesh**
2. Choose format: **STL (.stl)**
3. Save to: `simulator/data/cad/my_egg.stl`
4. Note: STL is lower resolution but more universally supported

### Option C: URDF (For Mechanisms)

If your design includes internal mechanisms:
1. **Export Assembly as URDF**
   - File → Export → URDF
   - Save to: `simulator/data/cad/my_egg_mechanism.urdf`
2. This preserves joint definitions and multi-body structure

## Step 3: Create Configuration File

In `config/egg_models/my_egg.yaml`, create:

```yaml
name: my_egg_500g
description: Custom egg design from Fusion 360

# Geometry settings
geometry:
  profile: CAD  # Use actual CAD file
  cad_file: data/cad/my_egg.step
  cad_scale: 1.0  # Scale factor if needed
  contact_radius: 35  # mm
  surface_roughness: 0.1  # mm
  shell_thickness: 2  # mm

# Physical properties (from Fusion 360 mass analysis)
mass:
  total: 500  # grams
  center_of_mass: [x, y, z]  # mm, relative to geometric center
  inertia_tensor:  # 3x3 matrix, g·mm²
    - [Ixx, Ixy, Ixz]
    - [Iyx, Iyy, Iyz]
    - [Izx, Izy, Izz]
```

### Example (Filled In)

```yaml
name: egg_500g_v1
description: Standard test egg, 500g, bottom-heavy

geometry:
  profile: CAD
  cad_file: data/cad/egg_model_v1.step
  cad_scale: 1.0
  contact_radius: 35
  surface_roughness: 0.1
  shell_thickness: 2.5

mass:
  total: 500
  center_of_mass: [0, 0, -25]  # 25mm below center
  inertia_tensor:
    - [105000, 0, 0]
    - [0, 105000, 0]
    - [0, 0, 90000]
```

## Step 4: Verify in Simulator

Test that your CAD loads correctly:

```python
from src.cad_importer import CADImporter
from src.egg_model import EggModel

# Load CAD geometry
cad_mesh = CADImporter.import_file('data/cad/my_egg.step', name='my_egg')

# Create egg model
config = {
    'name': 'my_egg',
    'geometry': {
        'profile': 'CAD',
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
print(egg.summary())
```

## Step 5: Run Simulation with Your Model

```bash
python experiments/baseline_tests.py \
    --model config/egg_models/my_egg.yaml \
    --target-angle 15 \
    --duration 30 \
    --output results/my_egg_study.json
```

## Troubleshooting

### "CAD file not found"
- Ensure file path is relative to simulator root directory
- Use forward slashes: `data/cad/egg.step`

### "Geometry looks wrong"
- Check scale factor (STEP files may be in mm or cm)
- Verify contact radius matches actual egg size
- Visualize with: `python -c "from src.cad_importer import CADImporter; mesh = CADImporter.import_file('path/to/file'); print(mesh.get_bounds())"`

### "Mass/CoM doesn't match"
- Verify Fusion 360 mass properties calculation
- Ensure center of mass is **below** geometric center (bottom-heavy)
- For asymmetric designs, confirm CoM offset in correct direction

### "Simulation runs slow"
- Reduce contact radius for simpler collision geometry
- Use STL instead of STEP (fewer polygons)
- Lower simulation resolution if not needed for control validation

## Best Practices

1. **Validate Geometry**
   - Check bounding box: should be ~70-80mm for typical egg
   - Verify CoM is 20-30mm below center
   - Ensure no missing surfaces or gaps

2. **Optimize for Simulation**
   - Simplify geometry if possible (fewer triangles = faster sim)
   - Remove internal details not needed for dynamics
   - Use CAD_SCALE parameter to adjust if needed

3. **Document Your Design**
   - Keep Fusion file alongside CAD export
   - Record mass properties in YAML config
   - Add comment with design intent

4. **Compare to Baseline**
   - Run baseline test with standard 500g egg first
   - Compare your results: if very different, check mass properties
   - Use baseline as reference for motor method performance

## Advanced: Custom Geometry Definition

If you don't have CAD, define parametrically:

```yaml
geometry:
  profile: ellipsoid  # or 'sphere'
  semi_axes: [35, 35, 40]  # a, b, c in mm
  resolution: 20  # polygon resolution

mass:
  total: 500
  center_of_mass: [0, 0, -25]
  inertia_tensor:
    - [105000, 0, 0]
    - [0, 105000, 0]
    - [0, 0, 90000]
```

Or load from Python:

```python
from src.egg_model import create_standard_egg

# Standard 500g egg with 25mm CoM offset
egg = create_standard_egg(mass_g=500, com_offset_mm=25)
```

## References

- Fusion 360 Mass Properties: https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-A85626BA-6945-4556-A193-B8EF39FAD6DA
- CAD formats: STEP (ISO 10303), STL (binary/ASCII), URDF (XML)
- Inertia tensor calculation: https://en.wikipedia.org/wiki/Moment_of_inertia
