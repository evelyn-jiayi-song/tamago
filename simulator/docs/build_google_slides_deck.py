#!/usr/bin/env python3
"""Build a Google Slides-importable technical deck from the project outline."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "simulator" / "docs"
ASSETS = DOCS / "assets"
OUT = DOCS / "WOBBLE_MECHANISMS_TECHNICAL_DECK.pptx"

# White canvas with Stanford-inspired Cardinal accents and a rainbow gradient.
BG = RGBColor(255, 255, 252)
PANEL = RGBColor(248, 249, 247)
PANEL2 = RGBColor(242, 244, 241)
TEXT = RGBColor(32, 37, 44)
MUTED = RGBColor(94, 103, 112)
CYAN = RGBColor(0, 126, 167)
AMBER = RGBColor(229, 132, 0)
GREEN = RGBColor(0, 132, 96)
RED = RGBColor(140, 21, 45)       # Stanford Cardinal-inspired
PURPLE = RGBColor(118, 67, 151)
BLUE = RGBColor(49, 91, 160)
PINK = RGBColor(204, 64, 112)


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.replace("#", ""))


def add_box(slide, x, y, w, h, fill=PANEL, line=None, radius=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y),
                                   Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line or fill
    return shape


def add_gradient_rule(slide, x=0.55, y=1.15, w=12.2, h=0.06):
    colors = (RED, PINK, PURPLE, BLUE, CYAN, GREEN, AMBER)
    segment = w / len(colors)
    for index, color in enumerate(colors):
        add_box(slide, x + index * segment, y, segment + 0.02, h, color)


def add_code(slide, code, x, y, w, h, accent=RED, size=12):
    add_box(slide, x, y, w, h, RGBColor(35, 39, 45), accent, radius=True)
    add_text(slide, code, x + 0.22, y + 0.18, w - 0.44, h - 0.32,
             size, RGBColor(244, 246, 242), font="Menlo")


def add_text(slide, text, x, y, w, h, size=18, color=TEXT, bold=False,
             align=PP_ALIGN.LEFT, font="Aptos", valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = valign
    p = frame.paragraphs[0]
    p.alignment = align
    for index, line in enumerate(str(text).split("\n")):
        if index:
            p = frame.add_paragraph()
            p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.name = font
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
    return box


def add_rich_text(slide, lines, x, y, w, h, size=16, color=TEXT,
                  spacing=5):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    for index, item in enumerate(lines):
        if isinstance(item, tuple):
            text, item_color, bold = item
        else:
            text, item_color, bold = item, color, False
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.space_after = Pt(spacing)
        run = p.add_run()
        run.text = text
        run.font.name = "Aptos"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = item_color
    return box


def add_header(slide, number, title, subtitle=None):
    add_text(slide, f"{number:02d}", 0.55, 0.35, 0.5, 0.3, 11, RED, True)
    add_text(slide, title, 1.15, 0.26, 11.6, 0.5, 25, TEXT, True)
    if subtitle:
        add_text(slide, subtitle, 1.17, 0.83, 11.3, 0.3, 11, MUTED)
    add_gradient_rule(slide)


def add_footer(slide, text="WOBBLE MECHANISMS  /  TECHNICAL PROTOTYPE"):
    add_text(slide, text, 0.58, 7.18, 8, 0.18, 8, MUTED)


def add_bullets(slide, bullets, x, y, w, h, size=16, accent=CYAN):
    lines = []
    for bullet in bullets:
        lines.append((f"•  {bullet}", TEXT, False))
    add_rich_text(slide, lines, x, y, w, h, size=size, spacing=8)


def add_image(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                    width=Inches(w) if w else None,
                                    height=Inches(h) if h else None)


def svg_png(svg_path: Path, temp_dir: Path) -> Path | None:
    """Rasterize an SVG when Cairo is available; otherwise use a labeled card."""
    try:
        import cairosvg
    except (ImportError, OSError):
        return None
    output = temp_dir / (svg_path.stem + ".png")
    cairosvg.svg2png(url=str(svg_path), write_to=str(output), output_width=1200)
    return output


def add_visual(slide, path, label, x, y, w, h):
    if path is not None:
        return add_image(slide, path, x, y, w=w)
    add_box(slide, x, y, w, h, PANEL2, CYAN, radius=True)
    add_text(slide, f"VISUAL ASSET\n{label}", x + 0.2, y + h / 2 - 0.35,
             w - 0.4, 0.7, 16, CYAN, True, PP_ALIGN.CENTER,
             valign=MSO_ANCHOR.MIDDLE)


def new_slide(prs, number, title, subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = BG
    add_header(slide, number, title, subtitle)
    add_footer(slide)
    return slide


def section_slide(prs, number, index, title, thesis, color):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG
    add_gradient_rule(slide, y=0.55, h=0.09)
    add_text(slide, f"{index}", 0.85, 1.25, 1.2, 0.8, 42, color, True)
    add_text(slide, title.upper(), 0.9, 2.25, 10.8, 0.7, 36, TEXT, True)
    add_text(slide, thesis, 0.95, 3.25, 8.5, 0.8, 21, MUTED)
    add_box(slide, 0.95, 5.45, 3.0, 0.16, color, color, radius=True)
    add_footer(slide, "WOBBLE MECHANISMS  /  CHAPTER")
    return slide


def build():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    with tempfile.TemporaryDirectory(prefix="wobble-deck-") as temp:
        temp_dir = Path(temp)
        architecture = svg_png(ASSETS / "system-architecture.svg", temp_dir)
        validation = svg_png(ASSETS / "physical-validation.svg", temp_dir)
        schematic = svg_png(ASSETS / "egg-unit-sheet1-schematic.svg", temp_dir)

        slide = prs.slides.add_slide(blank)
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = BG
        add_gradient_rule(slide, x=0.75, y=0.7, w=11.8, h=0.12)
        add_text(slide, "WOBBLE\nMECHANISMS", 0.75, 1.15, 6.3, 1.5, 42, RED, True)
        add_text(slide, "A mechatronic egg that turns imbalance into choreography",
                 0.8, 2.85, 7.2, 0.45, 18, CYAN, True)
        add_text(slide, "ESP32  ·  BNO055  ·  TMC2209  ·  stepper actuation  ·  laptop dashboard",
                 0.8, 3.55, 7.2, 0.35, 12, MUTED)
        for i, color in enumerate((RED, PINK, PURPLE, BLUE, CYAN, GREEN, AMBER)):
            add_box(slide, 8.25 + (i % 2) * 1.4, 1.55 + i * 0.48, 2.7, 0.28,
                    color, color, radius=True)
        add_text(slide, "A technical prototype for sensing, self-righting motion,\nand delayed response between two expressive objects.",
                 0.8, 5.55, 7.2, 0.7, 18, TEXT)
        add_footer(slide, "WOBBLE MECHANISMS  /  FINAL PRESENTATION SOURCE")

        # Overview / table of contents.
        slide = new_slide(prs, 2, "How to read this project", "Five chapters: from desire to evidence")
        toc = [("01", "ART MOTIVATIONS", "Why an egg should feel alive", RED),
               ("02", "TECHNICAL VISION", "What must be sensed, modeled, and controlled", BLUE),
               ("03", "REALIZATION + DEMO", "Firmware, dashboard, hardware, and measured behavior", GREEN),
               ("04", "FUTURE DIRECTIONS", "What must be instrumented next", AMBER),
               ("05", "LEARNING", "The assumptions that changed", PURPLE)]
        for i, (n, title, body, color) in enumerate(toc):
            y = 1.55 + i * 0.9
            add_text(slide, n, 0.95, y, 0.55, 0.3, 14, color, True)
            add_text(slide, title, 1.7, y - 0.02, 3.2, 0.3, 15, TEXT, True)
            add_text(slide, body, 5.0, y - 0.02, 5.9, 0.3, 14, MUTED)
            add_box(slide, 11.5, y + 0.05, 0.5, 0.16, color, color, radius=True)

        slide = section_slide(prs, 3, "01", "Art motivations",
                              "A small body becomes expressive when its constraints become gestures.", RED)
        slide = new_slide(prs, 4, "Product concept", "A self-righting object with a visible inner life")
        for i, (label, color) in enumerate((("IDLE", MUTED), ("INITIATE", CYAN),
                                             ("WOBBLE", AMBER), ("SETTLE", GREEN))):
            x = 0.8 + i * 3.0
            add_box(slide, x, 1.7, 2.2, 1.0, PANEL2, color, radius=True)
            add_text(slide, label, x, 1.95, 2.2, 0.25, 15, color, True, PP_ALIGN.CENTER)
            if i < 3:
                add_text(slide, "→", x + 2.32, 1.98, 0.4, 0.25, 22, MUTED, True)
        add_bullets(slide, ["Independent distance, smooth-distance, and rocking modes",
                            "IMU tare, stop, immediate stop, and clockwise origin return",
                            "Second egg can answer with a delayed, lower-intensity motion",
                            "Implemented behavior is verified; final product experience remains a design direction"],
                    0.9, 3.25, 6.0, 2.6)
        add_box(slide, 8.0, 3.1, 4.3, 2.1, PANEL2, CYAN, radius=True)
        add_text(slide, "TWO EGGS = A CONVERSATION", 8.3, 3.42, 3.7, 0.3, 14, CYAN, True)
        add_text(slide, "one initiates\none listens\none answers\nboth settle", 8.3, 3.95, 3.4, 1.1, 22, TEXT, True)

        slide = new_slide(prs, 5, "Why an egg?", "Passive self-righting becomes an active control problem")
        add_text(slide, "τgravity = m g dCoM sin(θ)", 0.95, 1.65, 5.5, 0.6, 27, AMBER, True)
        add_bullets(slide, ["Bottom-heavy geometry creates a restoring torque",
                            "The motor injects motion around the stable equilibrium",
                            "Tilt angle depends on mass distribution, contact, friction, and excitation",
                            "A static lean is not the same as a dynamic wobble"],
                    0.95, 2.6, 5.4, 2.7)
        add_box(slide, 7.1, 1.55, 4.8, 4.35, PANEL2, AMBER, radius=True)
        add_text(slide, "gravity ↓", 9.0, 1.85, 1.4, 0.3, 17, CYAN, True, PP_ALIGN.CENTER)
        add_box(slide, 8.7, 2.25, 1.6, 2.5, RGBColor(238, 226, 190), RGBColor(238, 226, 190), radius=True)
        add_box(slide, 9.1, 4.0, 0.8, 0.75, AMBER, AMBER, radius=True)
        add_text(slide, "CoM", 9.18, 4.2, 0.65, 0.2, 10, BG, True, PP_ALIGN.CENTER)
        add_text(slide, "contact point", 8.15, 5.15, 2.7, 0.25, 12, MUTED, False, PP_ALIGN.CENTER)
        add_text(slide, "θ", 10.9, 3.0, 0.3, 0.3, 22, CYAN, True)

        slide = section_slide(prs, 6, "02", "Technical vision",
                              "Make a physical intuition inspectable: geometry → sensing → control → evidence.", BLUE)
        slide = new_slide(prs, 7, "Iterations and design-space exploration", "From mechanism research to a working two-board prototype")
        add_bullets(slide, ["Explore ten actuation architectures",
                            "Model egg dynamics and motor methods",
                            "Add ESP32 + BNO055 + TMC2209 control",
                            "Build USB dashboard and independent board routing",
                            "Add peer filtering and delayed follower behavior",
                            "Prototype Wi-Fi, then return to USB for deterministic commissioning",
                            "Add live plots, session capture, and smooth motion"],
                    0.85, 1.55, 6.1, 4.9, size=17)
        add_box(slide, 7.65, 1.6, 4.4, 4.2, PANEL2, PURPLE, radius=True)
        add_text(slide, "10 explored architectures", 8.0, 1.95, 3.8, 0.35, 17, PURPLE, True)
        add_text(slide, "eccentric mass\nsolenoid slider\nEAP / hydraulic piston\nvoice coil / reactive pendulum\npiezo / SMA\nBLDC cam\nadaptive resonance", 8.0, 2.6, 3.5, 2.5, 16, TEXT)

        slide = new_slide(prs, 8, "Current prototype architecture", "Sensing, actuation, and laptop control")
        add_visual(slide, architecture, "system-architecture.svg", 0.8, 1.45, 7.4, 3.6)
        add_text(slide, "BNO055 → ESP32 MicroPython → TMC2209 STEP/DIR/EN → stepper → mechanism",
                 0.95, 5.35, 7.2, 0.4, 13, CYAN, True)
        add_bullets(slide, ["Egg A and Egg B have independent command paths",
                            "Telemetry returns IMU and motor state",
                            "Peer mode is relayed through the laptop",
                            "USB is the primary working transport"],
                    8.6, 1.8, 3.3, 2.6, size=16)

        slide = new_slide(prs, 9, "Final technical stack", "The prototype spans embedded, host, and communication layers")
        columns = [("EMBEDDED", ["ESP32 MicroPython", "BNO055-compatible IMU",
                                  "TMC2209 STEP/DIR", "Two-phase stepper"], CYAN),
                   ("HOST", ["Python + pyserial", "HTML / JavaScript dashboard",
                              "NumPy / SciPy", "PyBullet / Matplotlib"], AMBER),
                   ("COMMS", ["USB serial JSON", "Wi-Fi HTTP experiment",
                              "ESP-NOW logic prototype", "Laptop-relayed peer mode"], GREEN)]
        for i, (title, items, color) in enumerate(columns):
            x = 0.8 + i * 4.15
            add_box(slide, x, 1.7, 3.55, 3.9, PANEL2, color, radius=True)
            add_text(slide, title, x + 0.3, 2.05, 2.8, 0.3, 16, color, True)
            add_bullets(slide, items, x + 0.3, 2.65, 2.9, 2.4, size=16)

        slide = new_slide(prs, 10, "Dashboard concepts", "The UI is a measurement instrument, not just a remote control")
        definitions = [
            ("IMU", "Inertial Measurement Unit", "BNO055 estimates orientation, acceleration, and angular velocity."),
            ("GYRO", "Angular velocity", "How fast the body is rotating; reported in degrees per second."),
            ("ACCEL", "Specific force", "Includes gravity; dynamic acceleration estimates motion beyond ~1 g."),
            ("RPM", "Shaft speed", "Motor tempo; at 3200 steps/rev, RPM × 3200 / 60 = step rate."),
            ("TARE", "Reference pose", "Stores the current IMU reading as zero for relative orientation."),
            ("ORIGIN", "Motor pose", "Stores a shaft step reference; separate from IMU tare."),
        ]
        for i, (term, expansion, meaning) in enumerate(definitions):
            x = 0.75 + (i % 2) * 6.15
            y = 1.45 + (i // 2) * 1.45
            add_box(slide, x, y, 5.45, 1.05, PANEL2, [RED, CYAN, GREEN, AMBER, PURPLE, PINK][i], radius=True)
            add_text(slide, term, x + 0.25, y + 0.18, 1.0, 0.22, 14, [RED, CYAN, GREEN, AMBER, PURPLE, PINK][i], True)
            add_text(slide, expansion, x + 1.35, y + 0.18, 3.6, 0.22, 13, TEXT, True)
            add_text(slide, meaning, x + 0.25, y + 0.55, 4.8, 0.25, 11, MUTED)

        slide = new_slide(prs, 11, "Repository structure", "Where the system lives")
        tree = ("wobble_mechanisms/\n"
                "├── simulator/src/             physics and egg model\n"
                "├── simulator/firmware/        ESP32 firmware + BNO055\n"
                "├── simulator/dashboard/       USB bridge, UI, plots\n"
                "├── simulator/wifi_dashboard/  separate HTTP experiment\n"
                "├── simulator/dual_board/      peer / ripple logic\n"
                "├── simulator/wired_tests/     physical logs\n"
                "├── simulator/docs/            deck, diagrams, assets\n"
                "└── simulator/datasheet/       motor references")
        add_box(slide, 0.8, 1.55, 7.0, 4.8, PANEL2, CYAN, radius=True)
        add_text(slide, tree, 1.1, 1.9, 6.4, 4.1, 16, TEXT, font="Menlo")
        add_text(slide, "Color key", 8.55, 1.8, 2.0, 0.3, 15, TEXT, True)
        for i, (label, color) in enumerate((("model", CYAN), ("firmware", GREEN),
                                             ("physical tests", AMBER), ("coordination", PURPLE))):
            add_box(slide, 8.6, 2.35 + i * 0.7, 0.25, 0.25, color, color, radius=True)
            add_text(slide, label, 9.05, 2.3 + i * 0.7, 2.5, 0.3, 15, TEXT)

        slide = new_slide(prs, 12, "PCB / electronics integration", "A documented schematic, not yet a manufactured PCB")
        add_visual(slide, schematic, "egg-unit-sheet1-schematic.svg", 0.75, 1.5, 7.0, 3.6)
        add_bullets(slide, ["ESP32 controller",
                            "BNO055 I²C: SDA 21, SCL 22",
                            "TMC2209: STEP 25, DIR 26, ENN 27",
                            "Separate VMOT and regulated ESP32 logic supply",
                            "Common ground"],
                    8.25, 1.65, 3.9, 2.8, size=16)
        add_box(slide, 8.25, 4.85, 3.9, 0.85, PANEL2, RED, radius=True)
        add_text(slide, "STATUS: schematic / wiring asset\nNo verified layout, Gerbers, or manufactured PCB in repo.",
                 8.5, 5.05, 3.35, 0.45, 12, RED, True)

        slide = new_slide(prs, 13, "Motion primitives and units", "The firmware controls travel and timing; the IMU observes body motion")
        for i, (title, body, color) in enumerate((
            ("RUN", "one-way motion\nto target distance", CYAN),
            ("SMOOTH", "pre-target braking\nbefore endpoint", GREEN),
            ("ROCK", "alternating direction\nfinite or continuous", AMBER))):
            x = 0.8 + i * 4.15
            add_box(slide, x, 1.55, 3.55, 1.35, PANEL2, color, radius=True)
            add_text(slide, title, x + 0.25, 1.82, 1.4, 0.25, 16, color, True)
            add_text(slide, body, x + 1.55, 1.78, 1.7, 0.5, 14, TEXT, True)
        add_text(slide, "200 full steps/rev × 16 microsteps = 3200 commanded steps/rev", 1.0, 3.5, 11.2, 0.42, 22, CYAN, True, PP_ALIGN.CENTER)
        add_text(slide, "0.05 rev = 160 commanded steps       ·       1.00 rev = 3200 commanded steps",
                 1.15, 4.25, 10.9, 0.35, 16, TEXT, False, PP_ALIGN.CENTER)
        add_box(slide, 2.2, 5.1, 8.9, 0.75, PANEL2, AMBER, radius=True)
        add_text(slide, "Software steps are not proof of physical shaft motion without an encoder or marker.",
                 2.45, 5.34, 8.4, 0.25, 15, AMBER, True, PP_ALIGN.CENTER)

        slide = section_slide(prs, 14, "03", "Realization + demo",
                              "A command becomes pulses, pulses become motion, and motion becomes evidence.", GREEN)
        slide = new_slide(prs, 15, "Gyro, acceleration, speed, and rocking", "Four signals that describe different parts of a motion event")
        rows = [("GYROSCOPE", "angular velocity · °/s", "Primary peer-motion signal", CYAN),
                ("ACCELEROMETER", "specific force · includes gravity", "Dynamic motion beyond 1 g", GREEN),
                ("RPM", "motor shaft speed", "Tempo and inertial excitation", AMBER),
                ("ACCELERATION", "RPM change rate · RPM/s", "Gesture sharpness / vibration", PURPLE)]
        for i, (a, b, c, color) in enumerate(rows):
            y = 1.5 + i * 1.15
            add_box(slide, 0.9, y, 2.55, 0.78, color, color, radius=True)
            add_text(slide, a, 1.1, y + 0.23, 2.15, 0.24, 13, BG, True, PP_ALIGN.CENTER)
            add_text(slide, b, 3.85, y + 0.12, 3.25, 0.24, 15, TEXT, True)
            add_text(slide, c, 7.45, y + 0.12, 4.3, 0.35, 15, MUTED)
        add_text(slide, "dynamic_accel = abs(|accel| − 9.80665 m/s²)", 3.5, 6.2, 6.2, 0.35, 17, CYAN, True, PP_ALIGN.CENTER)

        slide = new_slide(prs, 16, "Smooth-motion visualization", "Normal motion versus controlled pre-target braking")
        add_box(slide, 0.9, 1.6, 5.5, 3.7, PANEL2, RED, radius=True)
        add_text(slide, "NORMAL", 1.25, 1.95, 2.0, 0.3, 17, RED, True)
        add_text(slide, "ramp → cruise → abrupt stop", 1.25, 2.45, 4.2, 0.35, 20, TEXT, True)
        add_text(slide, "Higher endpoint impulse\nMore excitation at reversal / stop", 1.25, 3.35, 4.2, 0.8, 15, MUTED)
        add_box(slide, 6.95, 1.6, 5.5, 3.7, PANEL2, GREEN, radius=True)
        add_text(slide, "SMOOTH DISTANCE", 7.3, 1.95, 3.0, 0.3, 17, GREEN, True)
        add_text(slide, "ramp → cruise → brake → settle", 7.3, 2.45, 4.5, 0.35, 20, TEXT, True)
        add_text(slide, "Uses remaining distance and acceleration\nto reduce endpoint impulse", 7.3, 3.35, 4.2, 0.8, 15, MUTED)
        add_text(slide, "Capture and plot with dashboard/capture_session.py and dashboard/plot_session.py",
                 1.2, 5.9, 10.9, 0.35, 15, CYAN, True, PP_ALIGN.CENTER)

        slide = new_slide(prs, 17, "Firmware realization", "The control loop is deliberately legible")
        add_text(slide, "Command parser → Stepper state machine → PWM frequency → telemetry", 0.9, 1.5, 11.2, 0.35, 17, TEXT, True)
        add_code(slide,
                 'if mode == "smooth_run":\n'
                 '    remaining = target_steps - abs(position_float_steps)\n'
                 '    braking_rpm = sqrt(remaining * 120 * accel / steps_per_rev)\n'
                 '    desired_rpm = min(cruise_rpm, braking_rpm)\n'
                 'ramp(rpm, desired_rpm, accel, dt)\n'
                 'pwm.freq(round(rpm * steps_per_rev / 60))',
                 0.9, 2.05, 6.1, 3.65, CYAN, 13)
        add_code(slide,
                 '{"cmd":"smooth_run","rpm":10,"accel":10,\n'
                 ' "distance_rev":0.05,"direction":1}\n\n'
                 '→ 160 commanded steps\n'
                 '→ telemetry at ~30 Hz',
                 7.35, 2.05, 4.7, 3.65, RED, 13)

        slide = new_slide(prs, 18, "Peer realization", "A ripple is a signal-processing pipeline, not a direct mirror")
        add_code(slide,
                 'gyro_score  = clamp(norm(gyro) / 90, 0, 1)\n'
                 'accel_score = clamp(dynamic_accel / 2.5, 0, 1)\n'
                 'raw = 0.70 * gyro_score + 0.30 * accel_score\n'
                 'filtered = EMA(raw, tau=0.18)\n'
                 'rock = hysteresis(filtered, start=.18, stop=.10)',
                 0.9, 1.65, 6.15, 3.7, PURPLE, 13)
        add_bullets(slide, ["250 ms intentional delay",
                            "Follower intensity defaults to 50%",
                            "Stale packets stop the follower",
                            "Duplicate rock starts are suppressed"],
                    7.55, 1.95, 4.0, 2.6, size=18)

        slide = new_slide(prs, 19, "Coordination algorithm", "A filtered, delayed, reduced-intensity response")
        steps = ["IMU sample", "gyro + dynamic accel", "weighted score", "EMA τ = 0.18 s",
                 "hysteresis", "250 ms delay", "50% follower", "rock intent"]
        for i, step in enumerate(steps):
            x = 0.65 + (i % 4) * 3.1
            y = 1.65 + (i // 4) * 1.25
            add_box(slide, x, y, 2.45, 0.7, PANEL2, PURPLE if i >= 4 else CYAN, radius=True)
            add_text(slide, step, x + 0.1, y + 0.22, 2.25, 0.22, 13, TEXT, True, PP_ALIGN.CENTER)
        add_text(slide, "gyro_score  = clamp(|gyro| / 90 dps, 0, 1)\n"
                 "accel_score = clamp(dynamic_accel / 2.5, 0, 1)\n"
                 "raw_score   = 0.70 gyro_score + 0.30 accel_score",
                 1.0, 4.35, 5.3, 1.4, 17, TEXT)
        add_box(slide, 7.1, 4.25, 4.9, 1.55, PANEL2, AMBER, radius=True)
        add_text(slide, "Safety behavior", 7.4, 4.55, 2.0, 0.25, 15, AMBER, True)
        add_text(slide, "sequence validation · stale timeout · duplicate suppression · local stop",
                 7.4, 4.95, 4.0, 0.5, 14, TEXT)

        slide = new_slide(prs, 20, "Live plots and physical validation", "Concrete unloaded-board evidence, with explicit limits")
        add_visual(slide, validation, "physical-validation.svg", 0.75, 1.45, 6.8, 3.6)
        add_bullets(slide, ["0.05 rev finite motion reached 160 steps",
                            "Continuous rocking stop latency: ~110–113 ms",
                            "Full-circle software runs reached ±3200 steps",
                            "IMU telemetry ran concurrently with PWM stepping",
                            "Observed unloaded-board temperature: ~31–32 °C"],
                    8.0, 1.65, 4.0, 2.8, size=16)
        add_box(slide, 8.0, 4.85, 4.0, 0.85, PANEL2, AMBER, radius=True)
        add_text(slide, "These results validate the command path and telemetry.\nThey do not certify loaded mechanics or missed-step rate.",
                 8.25, 5.05, 3.5, 0.45, 12, AMBER, True)

        slide = section_slide(prs, 21, "04", "Future directions",
                              "The next prototype should reduce uncertainty, not simply increase speed.", AMBER)
        slide = new_slide(prs, 22, "Failed attempts and engineering lessons", "Separating transport, power, software, and physical assumptions")
        lessons = [("WI-FI", "heartbeat watchdog + hotspot compatibility", RED),
                   ("POWER", "TMC VDD does not power the ESP32", AMBER),
                   ("MOTION", "software steps can advance without shaft motion", PURPLE),
                   ("IMU", "wiring, 3.3 V integrity, EMI, or address mismatch", CYAN)]
        for i, (title, body, color) in enumerate(lessons):
            x = 0.85 + (i % 2) * 6.1
            y = 1.65 + (i // 2) * 2.05
            add_box(slide, x, y, 5.35, 1.45, PANEL2, color, radius=True)
            add_text(slide, title, x + 0.28, y + 0.27, 1.4, 0.25, 15, color, True)
            add_text(slide, body, x + 1.7, y + 0.25, 3.25, 0.55, 15, TEXT, True)
        add_text(slide, "USB became the deterministic commissioning path; Wi-Fi remains a separate experiment.",
                 1.0, 6.05, 11.1, 0.3, 16, CYAN, True, PP_ALIGN.CENTER)

        slide = new_slide(prs, 23, "Validation boundary", "Simulation → unloaded board → loaded mechanism → product")
        stages = [("01", "SIMULATION", "model approximations", CYAN),
                  ("02", "UNLOADED BOARD", "command + telemetry", GREEN),
                  ("03", "LOADED MECHANISM", "tilt, thermal, missed steps", AMBER),
                  ("04", "PRODUCT", "repeatability + packaging", PURPLE)]
        for i, (n, title, body, color) in enumerate(stages):
            x = 0.7 + i * 3.1
            add_box(slide, x, 2.05, 2.55, 2.5, PANEL2, color, radius=True)
            add_text(slide, n, x + 0.22, 2.35, 0.45, 0.3, 19, color, True)
            add_text(slide, title, x + 0.22, 3.0, 2.1, 0.3, 14, TEXT, True)
            add_text(slide, body, x + 0.22, 3.6, 2.1, 0.45, 13, MUTED)
            if i < 3:
                add_text(slide, "→", x + 2.65, 3.05, 0.35, 0.3, 22, MUTED, True)
        add_text(slide, "Do not present simulated rankings or software position as final physical performance.",
                 1.15, 5.45, 10.9, 0.35, 16, AMBER, True, PP_ALIGN.CENTER)

        slide = new_slide(prs, 24, "Artistic vision", "Personality, sustained presence, and movement as conversation")
        add_text(slide, "The egg should feel like a small character.", 0.9, 1.45, 7.0, 0.5, 27, TEXT, True)
        add_text(slide, "Not a face. Not a voice. A recognizable way of moving.", 0.95, 2.05, 6.5, 0.35, 16, MUTED)
        add_bullets(slide, ["PERSONALITY  — cautious, curious, confident, tired",
                            "SUSTAINED MOVEMENT  — a state, not a one-shot trick",
                            "INTERCONNECTION  — listen, delay, answer, drift"],
                    1.0, 2.75, 5.8, 2.0, size=17)
        add_box(slide, 7.2, 1.55, 4.8, 3.4, PANEL2, RED, radius=True)
        add_text(slide, "MOTION AS RELATIONSHIP", 7.55, 1.92, 4.1, 0.25, 14, RED, True)
        add_text(slide, "Egg A moves\n      ↓ listen\nEgg B answers later\n      ↓ soften\nBoth settle / continue", 7.65, 2.5, 3.8, 1.8, 20, TEXT, True)
        add_text(slide, "Perfect synchronization = duplication\nDelay + variation = personality", 7.55, 4.35, 4.0, 0.42, 12, MUTED)
        for i, (label, meaning, color) in enumerate((("ACCELERATION", "gesture sharpness", CYAN),
                                                        ("RPM", "tempo", AMBER),
                                                        ("AMPLITUDE", "intensity", GREEN),
                                                        ("DELAY", "anticipation", PURPLE))):
            x = 7.0 + (i % 2) * 2.75
            y = 2.0 + (i // 2) * 1.45
            add_box(slide, x, y, 2.35, 0.95, PANEL2, color, radius=True)
            add_text(slide, label, x + 0.1, y + 0.18, 2.15, 0.2, 11, color, True, PP_ALIGN.CENTER)
            add_text(slide, meaning, x + 0.1, y + 0.52, 2.15, 0.2, 13, TEXT, True, PP_ALIGN.CENTER)

        slide = new_slide(prs, 25, "Future engineering steps", "The next milestone is proving loaded mechanical behavior")
        add_bullets(slide, ["Add a shaft marker or encoder; measure missed steps",
                            "Measure shell mass, center of mass, inertia, and linkage ratio",
                            "Validate ESP32 power and TMC current limits",
                            "Measure loaded tilt, natural frequency, temperature, repeatability",
                            "Create production PCB design with protection and test points",
                            "Mature peer transport after independent motion is reliable"],
                    1.0, 1.55, 6.4, 4.8, size=17)
        add_box(slide, 8.1, 1.7, 3.9, 3.8, PANEL2, GREEN, radius=True)
        add_text(slide, "PROTOTYPE", 8.55, 2.2, 2.8, 0.3, 18, CYAN, True, PP_ALIGN.CENTER)
        add_text(slide, "→", 9.95, 2.85, 0.5, 0.4, 26, MUTED, True, PP_ALIGN.CENTER)
        add_text(slide, "INSTRUMENTED\nPROTOTYPE", 8.55, 3.45, 2.8, 0.55, 18, AMBER, True, PP_ALIGN.CENTER)
        add_text(slide, "→", 9.95, 4.25, 0.5, 0.4, 26, MUTED, True, PP_ALIGN.CENTER)
        add_text(slide, "DEPLOYABLE\nOBJECT", 8.55, 4.85, 2.8, 0.55, 18, GREEN, True, PP_ALIGN.CENTER)

        slide = section_slide(prs, 26, "05", "Learning",
                              "The useful result is not a perfect wobble; it is a better question.", PURPLE)
        slide = new_slide(prs, 27, "What We Learned", "Live reflection slide")
        add_text(slide, "What surprised us?\n\nWhich assumption failed?\n\nWhat should the next prototype teach us?",
                 2.1, 1.65, 9.1, 3.5, 25, MUTED, False, PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_text(slide, "Intentionally left open for presentation notes and audience reflection.",
                 2.2, 5.9, 8.9, 0.3, 13, CYAN, True, PP_ALIGN.CENTER)

        slide = new_slide(prs, 28, "Appendix / references", "Evidence and implementation files")
        refs = ["simulator/docs/PRESENTATION_OUTLINE.md",
                "simulator/docs/TECHNICAL_PRESENTATION.md",
                "simulator/docs/assets/system-architecture.svg",
                "simulator/docs/assets/egg-unit-sheet1-schematic.svg",
                "simulator/docs/assets/physical-validation.svg",
                "simulator/wired_tests/physical_test_log.md",
                "simulator/dashboard/capture_session.py",
                "simulator/dashboard/plot_session.py",
                "simulator/dual_board/test_ripple_logic.py"]
        add_box(slide, 1.0, 1.6, 11.1, 4.6, PANEL2, CYAN, radius=True)
        add_text(slide, "\n".join(refs), 1.35, 1.95, 10.4, 3.8, 17, TEXT, font="Menlo")

    prs.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
