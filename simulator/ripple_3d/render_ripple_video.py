#!/usr/bin/env python3
"""Render a deterministic central-egg -> 4x4 receiver ripple to MP4.

The renderer is intentionally dependency-light: Pillow draws the frames and
the bundled Swift helper uses macOS AVFoundation to encode H.264 MP4. The
simulation is an explanatory radial coupling model, not a calibrated rigid
body solver.

Run from the repository root:

    python3 simulator/ripple_3d/render_ripple_video.py

The generated file is simulator/ripple_3d/output/ripple_4x4.mp4.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
OUTPUT_PATH = OUTPUT_DIR / "ripple_4x4.mp4"
ENCODER_SOURCE = ROOT / "encode_mp4.m"

WIDTH = 1280
HEIGHT = 720
FPS = 30
DURATION_S = 8.0
FRAME_COUNT = int(FPS * DURATION_S)

SOURCE_TIME_S = 0.50
SOURCE_AMPLITUDE = 1.00
PROPAGATION_SPEED_GRID_UNITS_S = 2.40
DAMPING_PER_GRID_UNIT = 0.72
GRID_PITCH_GRID_UNITS = 2.00
WOBBLE_DURATION_S = 1.20
WOBBLE_FREQUENCY_HZ = 2.80
SOURCE_DECAY_S = 1.65

# Receiver coordinates are a 4x4 lattice around a separate central source.
RECEIVERS = [(x, z) for z in (-3.0, -1.0, 1.0, 3.0)
             for x in (-3.0, -1.0, 1.0, 3.0)]

BG = (7, 14, 27)
PANEL = (12, 24, 42)
PANEL_2 = (17, 35, 57)
LINE = (50, 79, 105)
TEXT = (235, 244, 252)
MUTED = (157, 178, 199)
CYAN = (91, 224, 246)
CYAN_DIM = (26, 104, 132)
AMBER = (255, 180, 75)
GREEN = (129, 226, 180)
RED = (255, 120, 126)


def font(size: int, mono: bool = False):
    candidates = (
        "/System/Library/Fonts/Menlo.ttc" if mono else "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf" if mono else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


F_11 = font(11)
F_12 = font(12)
F_13 = font(13)
F_14 = font(14)
F_16 = font(16)
F_20 = font(20)
F_28 = font(28)
F_MONO_12 = font(12, mono=True)
F_MONO_15 = font(15, mono=True)


def rgba(color, alpha=255):
    return (*color, max(0, min(255, int(alpha))))


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, fill=TEXT, f=F_13, anchor=None):
    draw.text(xy, value, font=f, fill=fill, anchor=anchor)


def project(x, z):
    """Project a floor coordinate into the field panel."""
    return 390 + x * 84, 414 - z * 34 + (x + 3) * 5


def receiver_state(x, z, time_s):
    distance = math.hypot(x, z)
    arrival = SOURCE_TIME_S + distance / PROPAGATION_SPEED_GRID_UNITS_S
    hops_equivalent = distance / GRID_PITCH_GRID_UNITS
    amplitude = SOURCE_AMPLITUDE * DAMPING_PER_GRID_UNIT ** hops_equivalent
    age = time_s - arrival
    active = age >= 0.0 and age <= WOBBLE_DURATION_S
    envelope = max(0.0, 1.0 - age / WOBBLE_DURATION_S) if active else 0.0
    return distance, arrival, amplitude, age, envelope


def source_state(time_s):
    age = time_s - SOURCE_TIME_S
    active = age >= 0.0 and age <= WOBBLE_DURATION_S
    envelope = max(0.0, 1.0 - age / WOBBLE_DURATION_S) if active else 0.0
    return age, envelope


def draw_glow(base: Image.Image, center, radius, color, alpha=70):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow = ImageDraw.Draw(layer)
    for i in range(6, 0, -1):
        r = radius * i / 4.0
        glow.ellipse((center[0] - r, center[1] - r, center[0] + r, center[1] + r),
                     fill=rgba(color, alpha * (7 - i) / 7))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius / 2.7)))


def draw_egg(base: Image.Image, cx, base_y, scale, lean_deg, color, intensity,
             source=False, label=None):
    """Draw a shaded 2D egg with a fixed ground contact point and lean angle."""
    intensity = max(0.0, min(1.0, intensity))
    if intensity > 0.02:
        draw_glow(base, (cx, base_y - 32 * scale), 30 * scale * (0.75 + intensity), color,
                  35 + intensity * 100)

    draw = ImageDraw.Draw(base, "RGBA")
    shadow_w = 39 * scale * (1.0 + intensity * 0.12)
    rounded_shadow = (cx - shadow_w, base_y - 4 * scale, cx + shadow_w, base_y + 9 * scale)
    draw.ellipse(rounded_shadow, fill=(0, 0, 0, 105))
    angle = math.radians(lean_deg)
    # Local profile is anchored at (0, 0) at the floor contact point.
    profile = [(0, 0), (-14, -7), (-25, -25), (-29, -47), (-26, -70),
               (-17, -92), (-8, -108), (0, -119), (8, -108), (17, -92),
               (26, -70), (29, -47), (25, -25), (14, -7)]

    def transform(point):
        x, y = point[0] * scale, point[1] * scale
        return (cx + x * math.cos(angle) - y * math.sin(angle),
                base_y + x * math.sin(angle) + y * math.cos(angle))

    points = [transform(point) for point in profile]
    # Outer dark edge, body, then a soft highlight on the lit upper-left side.
    edge = tuple(max(0, int(v * 0.35)) for v in color)
    draw.polygon(points, fill=rgba(edge, 255), outline=rgba((2, 8, 15), 230))
    inner = [(cx + (px - cx) * 0.92, base_y + (py - base_y) * 0.92 - 2 * scale)
             for px, py in points]
    draw.polygon(inner, fill=rgba(color, 245))
    highlight = Image.new("RGBA", base.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight, "RGBA")
    hx, hy = transform((-9, -79))
    hd.ellipse((hx - 8 * scale, hy - 19 * scale, hx + 3 * scale, hy + 17 * scale),
               fill=(255, 255, 255, 42 + int(45 * intensity)))
    base.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(3 * scale)))
    if source:
        draw.ellipse((cx - 3 * scale, base_y - 121 * scale, cx + 3 * scale, base_y - 115 * scale),
                     fill=rgba((255, 238, 183), 210))
    if label:
        text(draw, (cx, base_y + 19 * scale), label, MUTED, F_11, anchor="mm")


def draw_arrow(draw, start, end, fill=CYAN, width=2):
    draw.line((start[0], start[1], end[0], end[1]), fill=fill, width=width)
    ang = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 8
    left = (end[0] - size * math.cos(ang - math.pi / 6), end[1] - size * math.sin(ang - math.pi / 6))
    right = (end[0] - size * math.cos(ang + math.pi / 6), end[1] - size * math.sin(ang + math.pi / 6))
    draw.polygon((end, left, right), fill=fill)


def draw_grid(base, time_s):
    draw = ImageDraw.Draw(base, "RGBA")
    source_xy = project(0, 0)

    # Floor guide and receiver grid axes.
    for x in (-3.0, -1.0, 1.0, 3.0):
        sx, sy = project(x, -4.0)
        ex, ey = project(x, 4.0)
        draw.line((sx, sy, ex, ey), fill=rgba(LINE, 100), width=1)
    for z in (-3.0, -1.0, 1.0, 3.0):
        sx, sy = project(-4.0, z)
        ex, ey = project(4.0, z)
        draw.line((sx, sy, ex, ey), fill=rgba(LINE, 100), width=1)

    source_age, source_env = source_state(time_s)
    wave_age = max(0.0, time_s - SOURCE_TIME_S)
    radius = wave_age * PROPAGATION_SPEED_GRID_UNITS_S * 84
    if 0 < radius < 420:
        for ring_scale, alpha in ((1.0, 150), (0.72, 80), (0.45, 38)):
            r = radius * ring_scale
            draw.ellipse((source_xy[0] - r, source_xy[1] - r * .42,
                          source_xy[0] + r, source_xy[1] + r * .42),
                         outline=rgba(CYAN, alpha), width=2)

    # Draw back-to-front so the near eggs overlap the floor guides naturally.
    for x, z in sorted(RECEIVERS, key=lambda point: project(*point)[1]):
        sx, sy = project(x, z)
        distance, arrival, amplitude, age, env = receiver_state(x, z, time_s)
        phase = max(0.0, age) * 2 * math.pi * WOBBLE_FREQUENCY_HZ
        lean = math.sin(phase) * amplitude * env * 24 + math.cos(phase * .61) * amplitude * env * 8
        visible_intensity = amplitude * env
        label = f"{amplitude:.2f}" if age >= 0 and age < WOBBLE_DURATION_S else None
        draw_egg(base, sx, sy, .66, lean, CYAN, visible_intensity, label=label)

    source_lean = math.sin(max(0.0, source_age) * 2 * math.pi * WOBBLE_FREQUENCY_HZ) * source_env * 30
    draw_egg(base, source_xy[0], source_xy[1], .86, source_lean, AMBER,
             source_env, source=True)

    # Source callout and directional cue.
    if time_s < SOURCE_TIME_S:
        callout = "SOURCE ARMED"
        callout_color = AMBER
    elif wave_age < 0.75:
        callout = "INPUT → COUPLING"
        callout_color = AMBER
    else:
        callout = "RADIAL WAVEFRONT"
        callout_color = CYAN
    rounded(draw, (source_xy[0] - 78, source_xy[1] - 160, source_xy[0] + 78, source_xy[1] - 132),
            8, fill=rgba(PANEL, 235), outline=rgba(callout_color, 160), width=1)
    text(draw, (source_xy[0], source_xy[1] - 146), callout, callout_color, F_11, anchor="mm")
    draw_arrow(draw, (source_xy[0], source_xy[1] - 130), (source_xy[0], source_xy[1] - 105), callout_color, 2)

    text(draw, (92, 128), "4 × 4 RECEIVER GRID", MUTED, F_12)
    text(draw, (92, 149), "distance-coded delay + damped wobble", TEXT, F_14)
    text(draw, (92, 586), "AMBER = source / CYAN = receivers / ring = advancing wavefront", MUTED, F_12)


def draw_panel(base, time_s):
    draw = ImageDraw.Draw(base, "RGBA")
    x0, y0, x1, y1 = 850, 26, 1250, 694
    rounded(draw, (x0, y0, x1, y1), 18, fill=rgba(PANEL, 245), outline=rgba(LINE, 210), width=1)
    text(draw, (878, 54), "WOBBLE / RIPPLE", CYAN, F_12)
    text(draw, (878, 78), "central source -> 4x4 field", TEXT, F_20)
    draw.line((878, 111, 1222, 111), fill=rgba(LINE, 190), width=1)

    text(draw, (878, 139), "SIMULATION STATE", MUTED, F_11)
    text(draw, (878, 164), "time", MUTED, F_12)
    text(draw, (1218, 164), f"{time_s:05.2f} s", TEXT, F_MONO_15, anchor="ra")
    wave_age = max(0.0, time_s - SOURCE_TIME_S)
    wave_radius = wave_age * PROPAGATION_SPEED_GRID_UNITS_S
    text(draw, (878, 189), "wavefront radius", MUTED, F_12)
    text(draw, (1218, 189), f"{wave_radius:04.2f} grid units", CYAN, F_MONO_12, anchor="ra")
    arrived = sum(1 for x, z in RECEIVERS if time_s >= receiver_state(x, z, time_s)[1])
    text(draw, (878, 214), "receivers reached", MUTED, F_12)
    text(draw, (1218, 214), f"{arrived:02d} / 16 eggs", TEXT, F_MONO_12, anchor="ra")

    rounded(draw, (878, 242, 1222, 356), 10, fill=rgba(PANEL_2, 235), outline=rgba(LINE, 150), width=1)
    text(draw, (896, 264), "KEY RELATIONSHIPS", MUTED, F_11)
    text(draw, (896, 288), "arrival", TEXT, F_12)
    text(draw, (1210, 288), "t_i = t_0 + d_i / v", CYAN, F_MONO_12, anchor="ra")
    text(draw, (896, 313), "amplitude", TEXT, F_12)
    text(draw, (1210, 313), "A_i = A_0 * D^(d_i / p)", CYAN, F_MONO_12, anchor="ra")
    text(draw, (896, 338), "energy proxy", TEXT, F_12)
    text(draw, (1210, 338), "E_i ~ A_i^2", AMBER, F_MONO_12, anchor="ra")

    text(draw, (878, 386), "ENERGY TRANSITION", MUTED, F_11)
    rounded(draw, (878, 402, 1222, 451), 9, fill=rgba((20, 54, 68), 220), outline=rgba(CYAN_DIM, 170), width=1)
    text(draw, (896, 427), "electrical input -> mechanical wobble -> coupled motion -> dissipation", TEXT, F_12, anchor="lm")
    text(draw, (878, 477), "CONTROL / OBSERVATION", MUTED, F_11)
    control_lines = [
        ("t₀", "0.50 s", "source trigger"),
        ("v", "2.40 grid units/s", "propagation speed"),
        ("D", "0.72× / grid unit", "distance damping"),
        ("f", "2.80 Hz", "wobble frequency"),
        ("τ", "1.20 s", "motion envelope"),
    ]
    y = 500
    for symbol, value, meaning in control_lines:
        text(draw, (878, y), symbol, AMBER if symbol == "t₀" else MUTED, F_MONO_12)
        text(draw, (910, y), value, TEXT, F_MONO_12)
        text(draw, (1218, y), meaning, MUTED, F_11, anchor="ra")
        y += 24
    text(draw, (878, 637), "All values are deterministic explanatory parameters.", MUTED, F_11)
    text(draw, (878, 656), "Coordinates: grid units · time: seconds · A: normalized", MUTED, F_11)


def render_frame(time_s):
    base = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    draw = ImageDraw.Draw(base, "RGBA")
    # Subtle horizon gradient bands keep the floor readable after video encode.
    for y in range(HEIGHT):
        mix = y / HEIGHT
        c = tuple(int(BG[i] * (1 - mix * .18) + (12, 31, 48)[i] * mix * .18) for i in range(3))
        draw.line((0, y, WIDTH, y), fill=(*c, 255))
    draw_grid(base, time_s)
    draw_panel(base, time_s)
    # Timeline marker: source trigger and current playback position.
    draw = ImageDraw.Draw(base, "RGBA")
    x0, x1, y = 92, 790, 624
    draw.line((x0, y, x1, y), fill=rgba(LINE, 220), width=2)
    for tick in range(0, 9, 2):
        x = x0 + (x1 - x0) * tick / DURATION_S
        draw.line((x, y - 5, x, y + 5), fill=rgba(MUTED, 160), width=1)
        text(draw, (x, y + 13), f"{tick} s", MUTED, F_11, anchor="ma")
    trigger_x = x0 + (x1 - x0) * SOURCE_TIME_S / DURATION_S
    draw.line((trigger_x, y - 13, trigger_x, y + 13), fill=AMBER, width=2)
    text(draw, (trigger_x, y - 19), "t₀", AMBER, F_11, anchor="ms")
    current_x = x0 + (x1 - x0) * min(time_s, DURATION_S) / DURATION_S
    draw.ellipse((current_x - 5, y - 5, current_x + 5, y + 5), fill=CYAN)
    return base.convert("RGB")


def run_encoder(raw_path: Path, output_path: Path):
    clang = shutil.which("clang")
    if not clang:
        raise RuntimeError("clang is required on macOS when Blender/ffmpeg are unavailable")
    with tempfile.TemporaryDirectory(prefix="ripple-encoder-") as temp:
        binary = Path(temp) / "encode_mp4"
        subprocess.run([
            clang, "-fobjc-arc", str(ENCODER_SOURCE), "-framework", "AVFoundation",
            "-framework", "CoreMedia", "-framework", "CoreVideo", "-framework", "Foundation",
            "-o", str(binary),
        ], check=True)
        subprocess.run([
            str(binary), str(raw_path), str(output_path),
            str(WIDTH), str(HEIGHT), str(FPS), str(FRAME_COUNT),
        ], check=True)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ripple-frames-") as temp:
        raw_path = Path(temp) / "frames.rgba"
        with raw_path.open("wb") as raw:
            for index in range(FRAME_COUNT):
                time_s = index / FPS
                raw.write(render_frame(time_s).tobytes())
                if (index + 1) % FPS == 0:
                    print(f"rendered {index + 1:03d}/{FRAME_COUNT} frames", flush=True)
        run_encoder(raw_path, OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH}")
    print(f"duration={DURATION_S:.2f} s fps={FPS} resolution={WIDTH}x{HEIGHT}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"render failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
