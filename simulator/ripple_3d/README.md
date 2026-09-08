# Egg Ripple Lab

An isolated, browser-based 3D visualization of a 5×5 field of bottom-heavy
egg-like bodies. It does not connect to hardware and does not modify the USB,
Wi‑Fi, or dual-board systems.

## Run it

From the repository root:

```bash
python3 -m http.server 8092 --directory simulator/ripple_3d
```

Open <http://127.0.0.1:8092> in a browser. The Three.js modules are loaded from
jsDelivr, so the first page load needs internet access.

## Interactions

- **Push center** starts a wave from the balanced central egg.
- The 5×5 coordinate pads push any individual egg; clicking a mesh does the same.
- **Demo playback** runs a short sequence of center and off-center pushes.
- **Pause / Resume**, **Step 100 ms**, and **Reset** control playback.
- Sliders adjust push strength, propagation speed, and damping per hop.
- Drag to orbit the camera and scroll to zoom.

## Ripple model

The grid uses orthogonal Manhattan neighbors. A push at `(row, column)` creates
one arrival event for every egg:

```text
distance = |target_row - source_row| + |target_column - source_column|
arrival_time = push_time + distance / propagation_speed
amplitude = push_strength × damping^distance
```

Each egg wobbles for 900 ms after its arrival, with a fading sinusoidal tilt.
This is an explanatory visualization model, not a calibrated rigid-body
simulation. Measured IMU data and motor commands remain in the existing
hardware dashboards.

## Deterministic tests

```bash
cd simulator/ripple_3d
python3 -m unittest -v test_ripple_model
```

The tests cover grid neighbors, central push immediacy, distance-based timing,
damping, and reset behavior.
