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

## Exportable 4×4 ripple video

`render_ripple_video.py` creates a presentation-ready technical visualization
with one amber central source and sixteen cyan receiver eggs in a 4×4 lattice.
The expanding ring shows the delayed radial wavefront; receiver labels show the
distance-damped amplitude while each receiver is active.

Regenerate the video from the repository root with:

```bash
python3 simulator/ripple_3d/render_ripple_video.py
```

Output: `simulator/ripple_3d/output/ripple_4x4.mp4`

The export is deterministic and has a duration of **8.00 s**, **30 fps**, and
**1280×720 px** resolution. It uses Pillow for frame drawing and the bundled
`encode_mp4.m` helper with macOS AVFoundation for H.264 MP4 encoding. On this
machine, the system `clang` compiler and AVFoundation are the only additional
dependencies; Blender and a system `ffmpeg` executable are not required.

### Model shown in the export

The source trigger is at `t₀ = 0.50 s`. For receiver `i`, with radial distance
`dᵢ` in grid units, grid pitch `p = 2.00 grid units`, propagation speed
`v = 2.40 grid units/s`, and damping `D = 0.72× per grid unit`:

```text
tᵢ = t₀ + dᵢ / v
Aᵢ = A₀ · D^(dᵢ / p)
Eᵢ ∝ Aᵢ²
```

The energy story is intentionally explicit: electrical input → mechanical
wobble at the source → coupled motion at delayed receivers → dissipation.
`A₀ = 1.00 normalized tilt`, `f = 2.80 Hz`, and the wobble envelope duration
is `τ = 1.20 s`. These are explanatory parameters, not calibrated hardware
measurements. Coordinates use grid units and all time values use seconds.
