#!/usr/bin/env python3
"""Render a presentation-ready PNG map of the wobble_mechanisms repository."""

from pathlib import Path
import math
import textwrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "simulator" / "docs" / "assets" / "png" / "repository-architecture.png"

WIDTH, HEIGHT = 3840, 2160
BG = "#F4F7FA"
INK = "#18232D"
MUTED = "#5E6B77"
LINE = "#CBD5DE"
WHITE = "#FFFFFF"

BLUE = "#477A9E"
BLUE_TINT = "#EAF3F8"
AMBER = "#B97725"
AMBER_TINT = "#FFF3E2"
GREEN = "#3E8069"
GREEN_TINT = "#E8F4EF"
PURPLE = "#745997"
PURPLE_TINT = "#F0EBF8"
SLATE = "#62707C"
SLATE_TINT = "#EDF1F4"

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
FONT_REGULAR = FONT_DIR / "Arial.ttf"
FONT_BOLD = FONT_DIR / "Arial Bold.ttf"


def font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(path), size)


def wrap_line(draw, value, fnt, max_width):
    if not value:
        return [""]
    words = value.split()
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [value]


def wrapped_lines(draw, value, fnt, max_width):
    lines = []
    for raw in value.split("\n"):
        lines.extend(wrap_line(draw, raw, fnt, max_width))
    return lines


def draw_text(draw, xy, value, fnt, fill=INK, max_width=None, line_gap=6):
    x, y = xy
    lines = wrapped_lines(draw, value, fnt, max_width) if max_width else value.split("\n")
    line_height = fnt.size + line_gap
    for index, line in enumerate(lines):
        draw.text((x, y + index * line_height), line, font=fnt, fill=fill)
    return len(lines) * line_height - line_gap


def rounded_box(draw, box, fill, outline=LINE, radius=24, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw, start, end, color=SLATE, width=5, head=18):
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    left = (x2 - head * math.cos(angle - math.pi / 6),
            y2 - head * math.sin(angle - math.pi / 6))
    right = (x2 - head * math.cos(angle + math.pi / 6),
             y2 - head * math.sin(angle + math.pi / 6))
    draw.polygon(((x2, y2), left, right), fill=color)


def draw_panel(draw, x, y, width, height, title, subtitle, tint, accent):
    rounded_box(draw, (x, y, x + width, y + height), tint, outline=accent, radius=30, width=3)
    draw.text((x + 30, y + 24), title, font=font(30, True), fill=INK)
    draw.text((x + 30, y + 67), subtitle, font=font(20), fill=MUTED)


def draw_box(draw, x, y, width, height, title, body, accent, fill=WHITE):
    rounded_box(draw, (x, y, x + width, y + height), fill, outline=LINE, radius=18, width=2)
    draw.rounded_rectangle((x, y, x + 12, y + height), radius=6, fill=accent)
    draw.text((x + 28, y + 18), title, font=font(24, True), fill=INK)
    draw_text(draw, (x + 28, y + 54), body, font(22), fill=MUTED,
              max_width=width - 52, line_gap=4)


def draw_vertical_stack(draw, x, y, width, boxes, accent, gap=12):
    positions = []
    cursor = y
    for title, body, height in boxes:
        draw_box(draw, x, cursor, width, height, title, body, accent)
        positions.append((cursor, height))
        cursor += height + gap
    for (top, height), (next_top, _next_height) in zip(positions, positions[1:]):
        arrow(draw, (x + width / 2, top + height + 2),
              (x + width / 2, next_top - 3), color=accent, width=4, head=14)


def draw_flow_lane(draw, y, label, steps, accent):
    x_label = 130
    label_w = 370
    step_x = 550
    step_w = 490
    step_h = 112
    gap = 32
    draw.text((x_label, y + 32), label, font=font(23, True), fill=accent)
    for index, step in enumerate(steps):
        x = step_x + index * (step_w + gap)
        rounded_box(draw, (x, y, x + step_w, y + step_h), WHITE, outline=accent, radius=16, width=2)
        draw_text(draw, (x + 22, y + 25), step, font(22, True), fill=INK,
                  max_width=step_w - 44, line_gap=4)
        if index < len(steps) - 1:
            arrow(draw, (x + step_w + 6, y + step_h / 2),
                  (x + step_w + gap - 7, y + step_h / 2), color=accent, width=4, head=14)


def main():
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    draw.text((130, 78), "WOBBLE MECHANISMS · REPOSITORY MAP",
              font=font(70, True), fill=INK)
    draw.text((134, 170),
              "A single codebase connecting physical design, simulation, firmware, peer coordination, validation, and presentation evidence",
              font=font(27), fill=MUTED)
    draw.text((2870, 92), "3840 × 2160 PNG",
              font=font(22, True), fill=MUTED)
    draw.text((2870, 130), "solid arrows = primary flow",
              font=font(20), fill=MUTED)
    draw.text((2870, 164), "group color = repository layer",
              font=font(20), fill=MUTED)
    draw.line((130, 240, 3710, 240), fill=LINE, width=3)

    # Shared data contract ribbon: this is the shortest way to read the whole repo.
    ribbon_y = 265
    draw.text((130, ribbon_y + 10), "SHARED DATA CONTRACT", font=font(20, True), fill=SLATE)
    ribbon_steps = [
        ("IMU telemetry\n° · °/s · m/s² · °C", BLUE),
        ("firmware\nJSON command surface", AMBER),
        ("transport\nUSB · Wi‑Fi · ESP‑NOW", PURPLE),
        ("runtime views\nplots · controls · status", GREEN),
        ("evidence\nlogs · tests · decks", SLATE),
    ]
    rx = 560
    rw = 560
    rh = 70
    for index, (label, color) in enumerate(ribbon_steps):
        rounded_box(draw, (rx, ribbon_y, rx + rw, ribbon_y + rh), WHITE, outline=color, radius=14, width=2)
        draw.multiline_text((rx + rw / 2, ribbon_y + rh / 2), label,
                            font=font(20, True), fill=INK, anchor="mm", align="center")
        if index < len(ribbon_steps) - 1:
            arrow(draw, (rx + rw + 8, ribbon_y + rh / 2),
                  (rx + rw + 78, ribbon_y + rh / 2), color=SLATE, width=4, head=14)
        rx += rw + 88

    panel_y = 375
    panel_h = 825
    margin = 130
    gap = 42
    panel_w = (WIDTH - 2 * margin - 3 * gap) // 4
    x_positions = [margin + i * (panel_w + gap) for i in range(4)]
    box_x_inset = 28
    box_w = panel_w - 56
    box_start_y = panel_y + 110

    draw_panel(draw, x_positions[0], panel_y, panel_w, panel_h,
               "01  DESIGN + PHYSICS", "model the egg before driving hardware", BLUE_TINT, BLUE)
    draw_vertical_stack(draw, x_positions[0] + box_x_inset, box_start_y, box_w, [
        ("REPOSITORY INTAKE",
         "QUICKSTART.md · MOTOR_CONTROL_PROPOSAL.md\nprompts/ agent briefs · requirements.txt", 108),
        ("CAD + EGG MODEL",
         "src/cad_importer.py → src/egg_model.py\nSTEP · STL · OBJ · URDF\ngeometry · mass · CoM · inertia", 126),
        ("RIGID-BODY SIMULATION",
         "src/physics_engine.py\nPyBullet · gravity 9.81 m/s² · Δt 0.001 s\ncontact · friction · damping · energy", 126),
        ("ACTUATION + METRICS",
         "motor_methods.py: MotorMethod + 10 strategies\nmetrics.py: precision · energy · robustness · mechanical viability", 132),
        ("EXPERIMENTS + RECORDS",
         "experiments/*.py → results/*.json\nbaseline tests · characterization", 106),
    ], BLUE)

    draw_panel(draw, x_positions[1], panel_y, panel_w, panel_h,
               "02  EMBEDDED CONTROL", "turn sensor readings into bounded motion", AMBER_TINT, AMBER)
    draw_vertical_stack(draw, x_positions[1] + box_x_inset, box_start_y, box_w, [
        ("PHYSICAL ELECTRONICS",
         "BNO055: accel m/s² · gyro °/s · orientation °\nTMC2209 STEP/DIR · NEMA stepper\nI²C 21/22 · STEP 25 · DIR 26 · EN 27", 132),
        ("USB FIRMWARE",
         "firmware/main.py + bno055.py\nMicroPython · newline JSON over USB serial\nstepper limits: RPM · RPM/s · steps/rev", 122),
        ("WI-FI FIRMWARE",
         "wifi_dashboard/firmware/main.py\nWiFiHTTP + Stepper + BNO055\nsame command surface, network transport", 112),
        ("PEER CONTROL CORE",
         "dual_board/ripple_logic.py\nMotionIntensityFilter → ReferencePublisher\nFollowerController → PeerEchoGate\n250 ms delay · 2 finite cycles · explicit stop", 152),
        ("PROTOTYPE ADAPTERS",
         "reference_node.py · follower_node.py\nespnow_transport.py: JSON · MAC · channel\nhost-testable, motor-output-free intent layer", 118),
    ], AMBER)

    draw_panel(draw, x_positions[2], panel_y, panel_w, panel_h,
               "03  RUNTIME APPS", "operate, observe, and relay the system", GREEN_TINT, GREEN)
    draw_vertical_stack(draw, x_positions[2] + box_x_inset, box_start_y, box_w, [
        ("USB DASHBOARD",
         "dashboard/server.py: SerialBridge · MultiSerialBridge\nindex.html: controls · telemetry · plots\nlocal HTTP API :8090", 126),
        ("WI-FI DASHBOARD",
         "wifi_dashboard/server.py\nPeerRelay · Proxy · Handler\nlaptop-relayed board API", 112),
        ("COMMISSIONING TOOLS",
         "start_usb_dashboard · board_diagnostic\nrun_motor_test · run_imu_feedback · run_led_flash\ncapture_session · plot_session", 142),
        ("LIVE DATA CONTRACT",
         "30 Hz telemetry: roll/pitch/heading °\naccel m/s² · gyro °/s · temperature °C\ncommands: rock / stop · RPM · RPM/s · rev", 142),
        ("TRANSPORT RELATIONSHIP",
         "USB serial = current wired path\nWi‑Fi = laptop relay path\nESP‑NOW = isolated direct peer prototype", 118),
    ], GREEN)

    draw_panel(draw, x_positions[3], panel_y, panel_w, panel_h,
               "04  VALIDATION + MEDIA", "turn behavior into evidence and reusable artifacts", PURPLE_TINT, PURPLE)
    draw_vertical_stack(draw, x_positions[3] + box_x_inset, box_start_y, box_w, [
        ("PHYSICAL VALIDATION",
         "wired_tests/\ncapture · coordinate_system · physical cases\nfull-circle · reverse · intensity logs", 126),
        ("DUAL-BOARD TESTS",
         "test_ripple_logic.py · simulate_ripple.py\nprotocol · stale-stop · echo-gate behavior", 112),
        ("RIPPLE VISUALIZATION",
         "ripple_3d/ripple_model.py + index.html\ndistance-delayed damped 5×5 explanatory field\nrender_ripple_video.py → output/ripple_4x4.mp4", 146),
        ("DOCS + SOURCE ASSETS",
         "docs/: CAD · physics · presentation · speech\nassets/: SVG + PNG · datasheet/ references", 122),
        ("PRESENTATION OUTPUTS",
         "build_google_slides_deck.py\nbuild_speech_script.py\ntechnical decks · speech script · MP4", 124),
    ], PURPLE)

    # Bottom lanes make the hierarchy operational: three ways to traverse the repo.
    flow_y = 1295
    draw.line((130, 1255, 3710, 1255), fill=LINE, width=3)
    draw.text((130, 1268), "HOW TO READ THE SYSTEM", font=font(21, True), fill=SLATE)
    draw_flow_lane(draw, flow_y, "SIMULATION LOOP", [
        "CAD + geometry", "EggModel\nmass · CoM", "PyBullet\nrigid body", "MotorMethod\nforce / torque", "Metrics\nprecision · energy", "results/*.json",
    ], BLUE)
    draw_flow_lane(draw, flow_y + 160, "HARDWARE LOOP", [
        "BNO055\nIMU", "ESP32\nMicroPython", "TMC2209 + NEMA\nSTEP / DIR", "USB or Wi‑Fi\nJSON API", "dashboard\nplots + controls",
    ], AMBER)
    draw_flow_lane(draw, flow_y + 320, "PEER RIPPLE LOOP", [
        "Egg A\nIMU input", "filter + publish\nintensity 0..1", "motion packet\n250 ms delay", "Egg B\nfollower + echo gate", "finite rock / stop\nRPM · RPM/s · rev",
    ], PURPLE)

    footer_y = 1905
    draw.line((130, footer_y, 3710, footer_y), fill=LINE, width=3)
    draw.text((130, footer_y + 28),
              "SOURCE OF TRUTH: executable modules and measured logs feed the dashboards, tests, video, and presentation outputs.",
              font=font(24, True), fill=INK)
    draw.text((130, footer_y + 70),
              "The direct peer adapter remains an isolated prototype; the current live path is USB serial, with Wi‑Fi as a laptop-relayed transport.",
              font=font(21), fill=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT, format="PNG", optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
