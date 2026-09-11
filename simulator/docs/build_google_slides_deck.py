#!/usr/bin/env python3
"""Build the Wobble Mechanisms technical deck.

The deck is generated from the repository so the technical narrative, units,
and diagrams can be revised alongside the prototype.  The source SVGs remain
editable repository assets; the deck embeds PNG derivatives for reliable
PowerPoint and Google Slides import.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "simulator" / "docs"
ASSETS = DOCS / "assets"
DEFAULT_OUT = DOCS / "WOBBLE_MECHANISMS_TECHNICAL_DECK_REBUILT.pptx"

# Existing project palette. The white canvas gives the technical hierarchy
# room to breathe; accents distinguish physics, control, sensing, and evidence.
BG = RGBColor(255, 255, 252)
PANEL = RGBColor(248, 249, 247)
PANEL2 = RGBColor(242, 244, 241)
TEXT = RGBColor(32, 37, 44)
MUTED = RGBColor(94, 103, 112)
CYAN = RGBColor(0, 126, 167)
AMBER = RGBColor(229, 132, 0)
GREEN = RGBColor(0, 132, 96)
RED = RGBColor(140, 21, 45)
PURPLE = RGBColor(118, 67, 151)
BLUE = RGBColor(49, 91, 160)
PINK = RGBColor(204, 64, 112)
INK = RGBColor(35, 39, 45)


def add_box(slide, x, y, w, h, fill=PANEL, line=None, radius=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(
        shape_type, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line or fill
    shape.line.width = Pt(1.1)
    return shape


def add_line(slide, x1, y1, x2, y2, color=MUTED, width=1.5, end_arrow=False):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1), Inches(y1), Inches(x2), Inches(y2),
    )
    line.line.color.rgb = color
    line.line.width = Pt(width)
    if end_arrow:
        line.line.end_arrowhead = True
    return line


def add_gradient_rule(slide, x=0.55, y=1.15, w=12.2, h=0.06):
    colors = (RED, PINK, PURPLE, BLUE, CYAN, GREEN, AMBER)
    segment = w / len(colors)
    for index, color in enumerate(colors):
        add_box(slide, x + index * segment, y, segment + 0.02, h, color, color)


def add_text(
    slide,
    text,
    x,
    y,
    w,
    h,
    size=18,
    color=TEXT,
    bold=False,
    align=PP_ALIGN.LEFT,
    font="Aptos",
    valign=MSO_ANCHOR.TOP,
    spacing=2,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.vertical_anchor = valign
    frame.margin_left = Inches(0.02)
    frame.margin_right = Inches(0.02)
    frame.margin_top = Inches(0.01)
    frame.margin_bottom = Inches(0.01)

    lines = str(text).split("\n")
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = align
        paragraph.space_after = Pt(spacing)
        run = paragraph.add_run()
        run.text = line
        run.font.name = font
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
    return box


def add_bullets(slide, bullets, x, y, w, h, size=17, color=TEXT, spacing=7):
    return add_text(
        slide,
        "\n".join(f"•  {item}" for item in bullets),
        x,
        y,
        w,
        h,
        size=size,
        color=color,
        spacing=spacing,
    )


def add_code(slide, code, x, y, w, h, accent=CYAN, size=15):
    add_box(slide, x, y, w, h, INK, accent, radius=True)
    return add_text(
        slide,
        code,
        x + 0.22,
        y + 0.16,
        w - 0.44,
        h - 0.28,
        size=size,
        color=RGBColor(244, 246, 242),
        font="Menlo",
        spacing=1,
    )


def add_header(slide, number, title, subtitle=None):
    add_text(slide, f"{number:02d}", 0.55, 0.34, 0.48, 0.28, 11, RED, True)
    add_text(slide, title, 1.15, 0.25, 11.55, 0.48, 25, TEXT, True)
    if subtitle:
        add_text(slide, subtitle, 1.17, 0.82, 11.2, 0.25, 11, MUTED)
    add_gradient_rule(slide)


def new_slide(prs, number, title, subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG
    add_header(slide, number, title, subtitle)
    return slide


def add_image(slide, path, x, y, w=None, h=None):
    return slide.shapes.add_picture(
        str(path),
        Inches(x),
        Inches(y),
        width=Inches(w) if w else None,
        height=Inches(h) if h else None,
    )


def rasterize_svg(svg_path: Path) -> Path | None:
    """Rasterize one repository SVG into the committed assets/png directory."""
    output_dir = ASSETS / "png"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{svg_path.stem}.png"
    converter = shutil.which("rsvg-convert") or "/opt/homebrew/bin/rsvg-convert"
    try:
        subprocess.run(
            [converter, "-w", "1800", "-o", str(output), str(svg_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return output if output.exists() else None


def crop_png(path: Path | None, suffix: str, box) -> Path | None:
    """Create a reproducible focus crop for dense repository diagrams."""
    if path is None:
        return None
    output = path.with_name(f"{path.stem}-{suffix}.png")
    try:
        with Image.open(path) as image:
            width, height = image.size
            left, top, right, bottom = box
            crop = image.crop((
                int(width * left), int(height * top),
                int(width * right), int(height * bottom),
            ))
            crop.save(output)
    except (OSError, ValueError):
        return None
    return output if output.exists() else None


def add_visual(slide, path, label, x, y, w, h):
    if path is not None:
        return add_image(slide, path, x, y, w=w)
    add_box(slide, x, y, w, h, PANEL2, CYAN, radius=True)
    return add_text(
        slide,
        f"VISUAL ASSET\n{label}",
        x + 0.2,
        y + h / 2 - 0.35,
        w - 0.4,
        0.7,
        16,
        CYAN,
        True,
        PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )


def add_flow_node(slide, x, y, w, h, label, detail, color, detail_size=13, label_size=15):
    add_box(slide, x, y, w, h, PANEL2, color, radius=True)
    add_text(slide, label, x + 0.12, y + 0.18, w - 0.24, 0.28, label_size, color, True, PP_ALIGN.CENTER)
    add_text(
        slide,
        detail,
        x + 0.14,
        y + 0.58,
        w - 0.28,
        h - 0.68,
        detail_size,
        TEXT,
        False,
        PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )


def add_metric(slide, x, y, w, h, label, value, unit, color, value_size=22):
    add_box(slide, x, y, w, h, PANEL2, color, radius=True)
    add_text(slide, label.upper(), x + 0.18, y + 0.16, w - 0.36, 0.22, 11, color, True)
    add_text(slide, value, x + 0.18, y + 0.47, w - 0.9, 0.42, value_size, TEXT, True)
    add_text(slide, unit, x + w - 0.75, y + 0.59, 0.55, 0.22, 12, MUTED, True, PP_ALIGN.RIGHT)


def add_table(slide, rows, x, y, w, h, col_widths, font_size=14, header_fill=INK):
    table_shape = slide.shapes.add_table(
        len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(h)
    )
    table = table_shape.table
    for index, ratio in enumerate(col_widths):
        table.columns[index].width = Inches(w * ratio)
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            cell = table.cell(row_index, col_index)
            cell.text = str(value)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if row_index == 0 else PANEL2
            for paragraph in cell.text_frame.paragraphs:
                paragraph.alignment = PP_ALIGN.LEFT
                for run in paragraph.runs:
                    run.font.name = "Aptos"
                    run.font.size = Pt(font_size if row_index else font_size - 1)
                    run.font.bold = row_index == 0
                    run.font.color.rgb = BG if row_index == 0 else TEXT
    return table_shape


def reorder_slides(prs, order):
    """Reorder generated slides and keep the small header index sequential."""
    slide_ids = list(prs.slides._sldIdLst)
    reordered = [slide_ids[index - 1] for index in order]
    for slide_id in slide_ids:
        prs.slides._sldIdLst.remove(slide_id)
    for slide_id in reordered:
        prs.slides._sldIdLst.append(slide_id)

    for number, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            if abs(shape.left - Inches(0.55)) > Inches(0.05):
                continue
            if abs(shape.top - Inches(0.34)) > Inches(0.05):
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.text.strip().isdigit():
                        run.text = f"{number:02d}"
                        break
                else:
                    continue
                break


def build(output: Path = DEFAULT_OUT):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    architecture = rasterize_svg(ASSETS / "system-architecture.svg")
    validation = rasterize_svg(ASSETS / "physical-validation.svg")
    schematic = rasterize_svg(ASSETS / "egg-unit-sheet1-schematic.svg")
    schematic_focus = crop_png(schematic, "focus", (0.03, 0.12, 0.78, 0.72))

    # 01. Cover
    slide = prs.slides.add_slide(blank)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = BG
    add_gradient_rule(slide, x=0.75, y=0.7, w=11.8, h=0.12)
    add_text(slide, "WOBBLE\nMECHANISMS", 0.75, 1.2, 5.6, 1.45, 42, RED, True)
    add_text(
        slide,
        "From restoring torque to a measured motion loop",
        0.8,
        2.9,
        7.2,
        0.4,
        19,
        CYAN,
        True,
    )
    add_text(
        slide,
        "ESP32 / BNO055 / TMC2209 / stepper actuation / USB dashboard",
        0.8,
        3.55,
        7.2,
        0.3,
        13,
        MUTED,
    )
    for i, color in enumerate((RED, PINK, PURPLE, BLUE, CYAN, GREEN, AMBER)):
        add_box(slide, 8.25 + (i % 2) * 1.4, 1.55 + i * 0.48, 2.7, 0.28, color, color, radius=True)
    add_text(
        slide,
        "A bottom-heavy body turns an internal torque command into visible motion.\nThe dashboard closes the loop with orientation, inertial, and motor state.",
        0.8,
        5.45,
        7.3,
        0.75,
        18,
        TEXT,
    )

    # 02. Principle / energy path
    slide = new_slide(prs, 2, "The motion loop", "The technical question is how input becomes measurable wobble")
    add_text(slide, "Command becomes useful when the physical response is observable.", 0.85, 1.45, 11.4, 0.38, 22, TEXT, True)
    add_text(slide, "FORWARD PATH", 0.85, 1.98, 1.8, 0.22, 13, CYAN, True)
    nodes = [
        (0.75, "COMMAND", "JSON over USB\n115200 bit/s", CYAN),
        (3.25, "CURRENT", "TMC2209 coil drive\nI [A]", BLUE),
        (5.75, "TORQUE", "Stepper shaft\nτ [N·m]", RED),
        (8.25, "REACTION", "Offset mass\nτreaction [N·m]", AMBER),
        (10.75, "WOBBLE", "Egg tilt\nθ [deg]", GREEN),
    ]
    for x, label, detail, color in nodes:
        add_flow_node(slide, x, 2.3, 1.8, 1.45, label, detail, color, detail_size=12)
    for x in (2.55, 5.05, 7.55, 10.05):
        add_line(slide, x, 3.02, x + 0.55, 3.02, color=MUTED, width=1.8, end_arrow=True)
    add_box(slide, 2.0, 4.55, 9.3, 1.2, PANEL2, PURPLE, radius=True)
    add_text(slide, "FEEDBACK / SAFETY", 2.3, 4.84, 2.2, 0.25, 15, PURPLE, True)
    add_text(slide, "BNO055: orientation θ [deg]   |   gyro ω [deg/s]   |   acceleration a [m/s²]   |   temperature T [°C]", 4.85, 4.84, 6.05, 0.3, 14, TEXT, True)
    add_line(slide, 9.9, 3.8, 9.9, 4.52, color=PURPLE, width=1.4, end_arrow=True)
    add_line(slide, 2.2, 4.52, 2.2, 3.8, color=PURPLE, width=1.4, end_arrow=True)
    add_text(slide, "Dashboard observes orientation, inertial, and motor state. Stable-rock safety + peer filtering use it; ordinary run/rock remains open-loop.", 0.9, 6.15, 11.55, 0.42, 14, CYAN, True, PP_ALIGN.CENTER)

    # 03. Restoring torque
    slide = new_slide(prs, 3, "Why the egg self-rights", "Gravity creates a restoring torque when the center of mass is offset")
    add_text(slide, "τg = −m g ℓCoM sin(θ)", 0.9, 1.5, 5.7, 0.55, 27, AMBER, True)
    add_text(slide, "τg [N·m]", 0.95, 2.2, 1.5, 0.25, 15, AMBER, True)
    add_bullets(slide, [
        "m [kg] is total body mass",
        "g = 9.81 [m/s²] is gravitational acceleration",
        "ℓCoM [m] is the contact-to-CoM lever arm used in the torque equation",
        "dCoM [m] is the modeled offset below geometric center; contact geometry remains to be measured",
        "θ [rad] is tilt from upright; θrad = θdeg × π/180 converts IMU output",
    ], 0.95, 2.65, 5.55, 2.65, size=16, spacing=5)
    add_text(slide, "Near upright: sin(θ) ≈ θ, so k_g = m g ℓCoM [N·m/rad].", 0.95, 5.55, 5.8, 0.55, 17, CYAN, True)

    add_box(slide, 7.0, 1.45, 4.9, 4.55, PANEL2, AMBER, radius=True)
    add_box(slide, 8.65, 2.0, 1.65, 2.9, RGBColor(238, 226, 190), RGBColor(238, 226, 190), radius=True)
    add_box(slide, 9.08, 4.0, 0.8, 0.7, AMBER, AMBER, radius=True)
    add_box(slide, 9.64, 3.0, 0.16, 0.16, RED, RED, radius=True)
    add_text(slide, "CoM", 9.12, 4.2, 0.7, 0.2, 10, BG, True, PP_ALIGN.CENTER)
    add_text(slide, "contact", 8.9, 5.08, 1.45, 0.22, 12, MUTED, False, PP_ALIGN.CENTER)
    add_line(slide, 9.72, 3.18, 9.72, 1.83, color=CYAN, width=1.6, end_arrow=True)
    add_text(slide, "gravity\nF = m g [N]", 9.95, 1.65, 1.3, 0.55, 14, CYAN, True)
    add_line(slide, 10.5, 3.15, 11.25, 3.15, color=AMBER, width=1.5, end_arrow=True)
    add_text(slide, "θ [deg]\nmeasured by IMU", 10.55, 3.45, 1.1, 0.6, 12, TEXT, True, PP_ALIGN.CENTER)
    add_text(slide, "Model example: m = 0.500 [kg], dCoM = 0.025 [m].", 7.35, 5.52, 4.2, 0.3, 13, TEXT, True, PP_ALIGN.CENTER)

    # 04. Rotational dynamics
    slide = new_slide(prs, 4, "The rotational physics", "Torque, angular speed, work, and power describe the actuator side")
    add_box(slide, 0.8, 1.5, 5.75, 4.55, PANEL2, RED, radius=True)
    add_text(slide, "TORQUE AND WORK", 1.15, 1.85, 3.3, 0.28, 16, RED, True)
    add_text(slide, "τ = r × F", 1.15, 2.35, 3.2, 0.42, 25, TEXT, True)
    add_text(slide, "τ [N·m]   r [m]   F [N]", 1.15, 2.9, 4.3, 0.25, 15, MUTED, True)
    add_text(slide, "W = ∫ τ dθ", 1.15, 3.5, 3.2, 0.38, 23, TEXT, True)
    add_text(slide, "W [J]   θ [rad]", 1.15, 4.0, 3.0, 0.25, 15, MUTED, True)
    add_text(slide, "A longer lever arm gives more rotational push for the same force.", 1.15, 4.72, 4.75, 0.62, 17, TEXT)

    add_box(slide, 6.85, 1.5, 5.65, 4.55, PANEL2, BLUE, radius=True)
    add_text(slide, "SPEED, POWER, AND GEARS", 7.2, 1.85, 4.4, 0.28, 16, BLUE, True)
    add_text(slide, "ω = 2π · RPM / 60", 7.2, 2.35, 4.6, 0.38, 22, TEXT, True)
    add_text(slide, "ω [rad/s]   RPM [rev/min]", 7.2, 2.83, 4.6, 0.25, 15, MUTED, True)
    add_text(slide, "Pmech = τ ω", 7.2, 3.4, 3.6, 0.38, 23, TEXT, True)
    add_text(slide, "Pmech [W]", 7.2, 3.88, 2.0, 0.25, 15, MUTED, True)
    add_text(slide, "Ideal reduction N [-]:  ωout = ωmotor / N\nτout ≈ ηg N τmotor  [N·m]", 7.2, 4.4, 4.75, 0.78, 17, TEXT)
    add_text(slide, "Gears trade speed for torque; ηg [-] captures loss.", 7.2, 5.45, 4.75, 0.3, 16, CYAN, True)
    add_text(slide, "Causal flow: F [N] → τ [N·m] → W [J] → ω [rad/s] → P [W] → geared output [N·m]", 1.0, 6.35, 11.25, 0.25, 14, CYAN, True, PP_ALIGN.CENTER)

    # 05. Energy transitions
    slide = new_slide(prs, 5, "Where the energy goes", "A command changes electrical energy into motion, storage, and dissipation")
    add_text(slide, "Energy transitions make the technical story testable: each arrow names a quantity we can measure or estimate.", 0.85, 1.45, 11.5, 0.38, 20, TEXT, True)
    energy_nodes = [
        (0.75, "ELECTRICAL INPUT", "Eelec = ∫ V I dt\nV [V], I [A], t [s] → E [J]", CYAN),
        (3.85, "MECHANICAL OUTPUT", "Pmech = τω\nτ [N·m], ω [rad/s] → P [W]", RED),
        (6.95, "MECHANICAL STATE", "K = ½ Jω² [J]\nΔU = m g d(1 − cos θ) [J]\nJ [kg·m²], d [m], θ [rad]", AMBER),
        (10.05, "DISSIPATION", "friction + damping\ncoil heat + sound [J]", PURPLE),
    ]
    for x, label, detail, color in energy_nodes:
        add_flow_node(slide, x, 2.35, 2.45, 1.55, label, detail, color, detail_size=12, label_size=13)
    for x in (3.35, 6.45, 9.55):
        add_line(slide, x, 3.12, x + 0.42, 3.12, color=MUTED, width=1.5, end_arrow=True)
    add_box(slide, 1.0, 4.65, 11.25, 1.1, PANEL2, GREEN, radius=True)
    add_text(slide, "EFFICIENCY QUESTION", 1.3, 4.98, 2.1, 0.25, 15, GREEN, True)
    add_text(slide, "ηsystem [-] = Pmech [W] / Pelec [W]", 3.65, 4.88, 3.9, 0.32, 21, TEXT, True)
    add_text(slide, "Electrical power, output torque, and loaded energy efficiency are not yet measured.", 7.75, 4.92, 4.05, 0.48, 14, TEXT, True)
    add_text(slide, "The next experiment instruments Vsupply [V], Isupply [A], torque [N·m], and body response θ [deg].", 1.0, 6.25, 11.25, 0.28, 15, CYAN, True, PP_ALIGN.CENTER)

    # 06. Components
    slide = new_slide(prs, 6, "Components inside one egg", "Each part owns one stage of the sensing-to-motion chain")
    components = [
        ("01", "BNO055", "IMU", "orientation [deg], acceleration [m/s²], gyro [deg/s]", CYAN),
        ("02", "ESP32", "controller", "parses JSON, schedules motion, emits telemetry", BLUE),
        ("03", "TMC2209", "driver", "regulates phase current [A] at a hardware-configured limit; STEP / DIR / ENN provide pulse, direction, enable", RED),
        ("04", "STEPPER", "actuator", "SM-17HS4023 ref: 0.7 [A/phase] → shaft torque [N·m]", AMBER),
        ("05", "MECHANISM", "body + offset mass", "converts internal reaction torque into tilt [deg]", GREEN),
    ]
    for i, (number, name, kind, role, color) in enumerate(components):
        y = 1.45 + i * 0.91
        add_box(slide, 0.85, y, 1.0, 0.63, color, color, radius=True)
        add_text(slide, number, 0.85, y + 0.18, 1.0, 0.23, 15, BG, True, PP_ALIGN.CENTER)
        add_text(slide, name, 2.15, y + 0.08, 2.1, 0.25, 19, color, True)
        add_text(slide, kind, 4.25, y + 0.1, 2.0, 0.22, 14, MUTED, True)
        add_text(slide, role, 6.15, y + 0.1, 6.0, 0.35, 16, TEXT, True)
        if i < len(components) - 1:
            add_line(slide, 1.35, y + 0.65, 1.35, y + 0.9, color=MUTED, width=1.0, end_arrow=True)
    add_text(slide, "BNO055 → ESP32 → TMC2209 → stepper → mechanism → BNO055", 1.1, 6.2, 11.0, 0.3, 17, CYAN, True, PP_ALIGN.CENTER)

    # 07. Electronics
    slide = new_slide(prs, 7, "Electronics integration", "The schematic is a wiring reference; the firmware test map is the current authority")
    add_visual(slide, schematic_focus or schematic, "egg-unit-sheet1-schematic-focus.png", 0.7, 1.45, 7.25, 4.2)
    add_text(slide, "SIGNALS", 8.35, 1.55, 1.5, 0.25, 15, CYAN, True)
    add_bullets(slide, [
        "I²C: SDA GPIO 21, SCL GPIO 22",
        "I²C clock: 100 [kHz]",
        "Firmware test map: STEP GPIO 25, DIR GPIO 26",
        "ENN GPIO 27, active low",
    ], 8.35, 1.95, 4.0, 1.85, size=16, spacing=5)
    add_text(slide, "POWER", 8.35, 4.05, 1.5, 0.25, 15, AMBER, True)
    add_bullets(slide, [
        "12 [V] motor reference; verify installed supply; asset labels 10 [V]",
        "Logic 3.3 [V] + common ground",
        "Bulk cap 100 [µF] / ≥25 [V]; EN pull-up 10 [kΩ]",
        "SM-17HS4023 motor reference: 0.7 [A/phase]",
        "TMC2209 current limit: not recorded; verify setting",
    ], 8.35, 4.4, 4.2, 1.4, size=12.5, spacing=2)
    add_box(slide, 8.35, 5.76, 4.2, 0.7, PANEL2, AMBER, radius=True)
    add_text(slide, "AS-BUILT NOTE\nSchematic pin map unreconciled; test map: STEP 25 / ENN 27.", 8.58, 5.88, 3.75, 0.5, 10.5, TEXT, True)

    # 08. Codespace setup
    slide = new_slide(prs, 8, "Codespace setup and rationale", "Parallel layers are joined by explicit interfaces, not a serial software pipeline")
    add_box(slide, 0.75, 1.45, 11.85, 0.7, INK, INK, radius=True)
    add_text(slide, "SHARED CONTRACT: newline-delimited JSON commands and telemetry", 1.0, 1.68, 11.35, 0.25, 17, BG, True, PP_ALIGN.CENTER)
    code_nodes = [
        (0.75, "simulator/src/", "physics model\nmetrics", CYAN),
        (3.75, "simulator/firmware/", "IMU + PWM\nstate machine", BLUE),
        (6.75, "simulator/dashboard/", "USB bridge\nplots + controls", GREEN),
        (9.75, "simulator/dual_board/", "filter + delay\npeer intent", PURPLE),
    ]
    for x, label, detail, color in code_nodes:
        add_flow_node(slide, x, 2.72, 2.55, 1.35, label, detail, color, detail_size=13)
    for x in (3.3, 6.3, 9.3):
        add_line(slide, x, 3.4, x + 0.4, 3.4, color=MUTED, width=1.5, end_arrow=True)
    add_box(slide, 2.15, 4.7, 8.95, 1.05, PANEL2, AMBER, radius=True)
    add_text(slide, "WHY THIS SPLIT", 2.45, 5.02, 2.0, 0.25, 15, AMBER, True)
    add_text(slide, "Test physics without hardware.\nIsolate transport from motion.\nTrace each run to one command and one log.", 4.5, 4.88, 6.1, 0.62, 14, TEXT)
    add_text(slide, "Interfaces: physics ↔ experiments; firmware ↔ dashboard; dashboard → peer filter; tests → evidence.", 1.1, 6.25, 11.1, 0.25, 15, CYAN, True, PP_ALIGN.CENTER)

    # 09. Runtime architecture
    slide = new_slide(prs, 9, "Runtime architecture", "Two independent USB channels share the same control contract")
    add_visual(slide, architecture, "system-architecture.png", 0.7, 1.4, 7.2, 4.0)
    add_text(slide, "WORKING PATH", 8.35, 1.55, 2.0, 0.25, 15, GREEN, True)
    add_bullets(slide, [
        "Laptop dashboard routes commands by board ID",
        "Each board emits telemetry at about 30 [samples/s]",
        "Serial link: 115200 [bit/s] JSON",
        "USB is the deterministic commissioning transport",
    ], 8.35, 1.95, 4.05, 2.05, size=16, spacing=5)
    add_text(slide, "OPTIONAL PEER PATH", 8.35, 4.35, 2.8, 0.25, 15, PURPLE, True)
    add_text(slide, "Laptop-mediated: features → filter → 250 [ms] delay → rock intent.\nBoth eggs remain independently addressable.", 8.35, 4.78, 4.0, 0.62, 15, TEXT, True)
    add_text(slide, "Board commands remain independently addressable.", 8.35, 5.63, 4.0, 0.25, 14, CYAN, True)

    # 10. Command inputs
    slide = new_slide(prs, 10, "Command surface", "Every numeric input maps to a physical or timing quantity")
    rows = [
        ("INPUT", "UNIT", "EFFECT"),
        ("mode", "enum", "run, smooth run, rock, smooth rock, stable rock (tilt limit)"),
        ("distance_rev", "shaft rev", "one-way travel target"),
        ("amplitude_rev", "shaft rev", "one-way rock amplitude"),
        ("rpm", "rev/min", "peak shaft speed"),
        ("accel", "rev/min/s", "speed ramp slope"),
        ("direction", "sign [-]", "+1 clockwise, −1 counter-clockwise"),
        ("cycles", "cycles [-]", "rock repetitions; 0 means continuous"),
        ("max_tilt_deg", "deg", "stable-rock tilt ceiling"),
        ("intensity", "fraction [-]", "rock command scale from 0 to 1"),
        ("target_fraction", "fraction [-]", "peer follower scale; default 0.50"),
    ]
    add_table(slide, rows, 0.75, 1.42, 11.85, 4.85, [0.24, 0.22, 0.54], font_size=14)
    add_text(slide, "Actions without numeric inputs: tare IMU, stop, stop immediately, record origin, return to origin.", 1.0, 6.5, 11.2, 0.25, 15, CYAN, True, PP_ALIGN.CENTER)

    # 11. Dashboard measurements
    slide = new_slide(prs, 11, "Dashboard measurements", "The UI exposes orientation, inertial, thermal, and motor state")
    add_text(slide, "IMU MEASUREMENTS", 0.85, 1.45, 2.3, 0.25, 15, CYAN, True)
    imu_rows = [
        ("heading / yaw", "orientation about vertical", "deg"),
        ("roll, pitch", "body orientation relative to tare", "deg"),
        ("accel x / y / z", "specific force, includes gravity", "m/s²"),
        ("gyro x / y / z", "angular velocity", "deg/s"),
        ("temperature", "sensor / board thermal reading", "°C"),
        ("calibration", "BNO055 status per subsystem", "0–3"),
    ]
    for i, (name, meaning, unit) in enumerate(imu_rows):
        y = 1.9 + i * 0.62
        add_text(slide, name, 0.95, y, 2.0, 0.22, 15, TEXT, True)
        add_text(slide, meaning, 3.05, y, 3.0, 0.22, 14, MUTED)
        add_text(slide, f"[{unit}]", 6.15, y, 0.9, 0.22, 14, CYAN, True)
    add_text(slide, "MOTOR AND TIMING STATE", 7.55, 1.45, 3.2, 0.25, 15, AMBER, True)
    motor_rows = [
        ("rpm / target_rpm", "shaft speed / target", "rev/min"),
        ("accel_rpm_s", "speed ramp", "rev/min/s"),
        ("position_steps", "commanded position", "steps"),
        ("distance_rev", "commanded travel", "shaft rev"),
        ("target_steps", "finite travel target", "steps"),
        ("step_rate_hz", "STEP pulse rate", "steps/s"),
        ("t_ms", "sample timestamp", "ms"),
        ("telemetry_hz", "stream rate", "samples/s"),
    ]
    for i, (name, meaning, unit) in enumerate(motor_rows):
        y = 1.9 + i * 0.54
        add_text(slide, name, 7.65, y, 2.15, 0.22, 14, TEXT, True)
        add_text(slide, meaning, 9.75, y, 1.55, 0.22, 12, MUTED)
        add_text(slide, f"[{unit}]", 11.28, y, 1.1, 0.22, 12, AMBER, True, PP_ALIGN.RIGHT)
    add_text(slide, "Position is generated-step state; IMU angles are body orientation.", 1.1, 6.22, 11.1, 0.25, 15, PURPLE, True, PP_ALIGN.CENTER)

    # 12. Dashboard physics vocabulary
    slide = new_slide(prs, 12, "Physics vocabulary in the dashboard", "Raw sensor fields become interpretable motion features")
    glossary = [
        ("GYROSCOPE", "ω [deg/s]", "Angular velocity.\nLarge magnitude means rapid rotation."),
        ("ACCELEROMETER", "a [m/s²]", "Specific force.\nA still sensor is near g = 9.81 [m/s²]."),
        ("DYNAMIC ACCEL", "adyn [m/s²]", "Motion beyond gravity.\nadyn = |‖a‖ − g|."),
        ("EULER ANGLES", "yaw / roll / pitch [deg]", "Orientation coordinates.\nTare makes them relative to a pose."),
    ]
    for i, (term, unit, meaning) in enumerate(glossary):
        x = 0.8 + (i % 2) * 6.15
        y = 1.55 + (i // 2) * 2.05
        color = (CYAN, GREEN, AMBER, PURPLE)[i]
        add_box(slide, x, y, 5.45, 1.45, PANEL2, color, radius=True)
        add_text(slide, term, x + 0.28, y + 0.2, 2.8, 0.25, 16, color, True)
        add_text(slide, unit, x + 3.05, y + 0.2, 2.0, 0.25, 14, TEXT, True, PP_ALIGN.RIGHT)
        add_text(slide, meaning, x + 0.28, y + 0.65, 4.85, 0.52, 16, TEXT)
    add_text(slide, "Peer detection uses gyro magnitude first, then dynamic acceleration to reject a stationary tilt.", 1.05, 6.0, 11.0, 0.35, 17, CYAN, True, PP_ALIGN.CENTER)

    # 13. Motion primitives and units
    slide = new_slide(prs, 13, "Motion primitives and conversion", "The firmware commands shaft travel; the mechanism determines the resulting tilt")
    primitives = [
        ("RUN", "one-way travel\nto distance_rev", CYAN),
        ("SMOOTH RUN", "one-way travel\nwith braking", GREEN),
        ("ROCK", "alternate direction\nfor cycles", AMBER),
        ("TILT-LIMITED ROCK", "continuous motion\nwith over-tilt safety", PURPLE),
    ]
    for i, (title, body, color) in enumerate(primitives):
        x = 0.7 + i * 3.1
        add_box(slide, x, 1.55, 2.55, 1.25, PANEL2, color, radius=True)
        add_text(slide, title, x + 0.15, 1.82, 2.25, 0.24, 15, color, True, PP_ALIGN.CENTER)
        add_text(slide, body, x + 0.2, 2.2, 2.15, 0.4, 14, TEXT, True, PP_ALIGN.CENTER)
    add_text(slide, "200 [full steps/rev] × 16 [microsteps/full step] = 3200 [commanded steps/rev]", 0.95, 3.55, 11.3, 0.42, 21, CYAN, True, PP_ALIGN.CENTER)
    add_text(slide, "step_rate = RPM × 3200 / 60", 2.0, 4.2, 9.3, 0.38, 23, TEXT, True, PP_ALIGN.CENTER)
    add_text(slide, "step_rate [steps/s]   RPM [rev/min]", 2.65, 4.7, 8.0, 0.25, 15, MUTED, True, PP_ALIGN.CENTER)
    add_metric(slide, 1.15, 5.35, 3.35, 0.82, "distance (shaft)", "0.05", "rev", CYAN)
    add_metric(slide, 4.95, 5.35, 3.35, 0.82, "commanded travel", "160", "steps", BLUE)
    add_metric(slide, 8.75, 5.35, 3.35, 0.82, "commanded shaft angle", "18", "deg", AMBER)

    # 14. Smooth motion
    slide = new_slide(prs, 14, "Smooth distance control", "Braking begins before the endpoint so the command does not cut off at cruise speed")
    add_text(slide, "REMAINING STEPS [steps] ↓", 0.9, 1.5, 3.3, 0.25, 14, MUTED, True)
    add_code(slide, "braking_rpm = sqrt(\n  remaining_steps × 120 × accel / steps_per_rev)\ntarget_rpm = min(cruise_rpm, braking_rpm)\nstep_rate [steps/s] =\n  target_rpm × steps_per_rev / 60", 0.85, 1.9, 6.2, 2.35, GREEN, 13)
    add_text(slide, "CONTROL LAW", 1.1, 4.32, 2.0, 0.25, 14, GREEN, True)
    add_text(slide, "120 = 2 × 60 [s/min]   remaining_steps [steps]   accel [rev/min/s]   steps_per_rev [steps/rev]", 1.1, 4.72, 5.95, 0.42, 12, MUTED)

    add_text(slide, "NORMAL RUN", 7.55, 1.55, 2.0, 0.25, 15, RED, True)
    for i, label in enumerate(("RAMP", "CRUISE", "CUT")):
        x = 7.55 + i * 1.55
        add_flow_node(slide, x, 2.0, 1.25, 0.85, label, "", RED if i == 2 else CYAN, detail_size=11)
        if i < 2:
            add_line(slide, x + 1.28, 2.42, x + 1.5, 2.42, color=MUTED, width=1.2, end_arrow=True)
    add_text(slide, "SMOOTH RUN", 7.55, 3.35, 2.0, 0.25, 15, GREEN, True)
    for i, label in enumerate(("RAMP", "CRUISE", "BRAKE", "SETTLE")):
        x = 7.55 + i * 1.18
        add_flow_node(slide, x, 3.8, 1.0, 0.85, label, "", GREEN if i >= 2 else CYAN, detail_size=10, label_size=12)
        if i < 3:
            add_line(slide, x + 1.02, 4.22, x + 1.14, 4.22, color=MUTED, width=1.2, end_arrow=True)
    add_text(slide, "The input is a speed ramp; the output is lower endpoint impulse.", 7.55, 5.28, 4.8, 0.55, 17, TEXT, True)

    # 15. Firmware realization
    slide = new_slide(prs, 15, "Firmware realization", "A small state machine turns JSON fields into bounded pulse timing")
    layers = [
        ("JSON PARSER", "command + numeric fields [units]", CYAN),
        ("STEPPER STATE", "mode + position [steps]", BLUE),
        ("PWM OUTPUT", "STEP [steps/s] + DIR + ENN", RED),
        ("TELEMETRY", "IMU + motor state / 33 [ms]", GREEN),
    ]
    for i, (label, detail, color) in enumerate(layers):
        y = 1.55 + i * 0.95
        add_box(slide, 0.85, y, 4.45, 0.67, PANEL2, color, radius=True)
        add_text(slide, label, 1.1, y + 0.2, 1.35, 0.22, 13, color, True)
        add_text(slide, detail, 2.5, y + 0.17, 2.45, 0.28, 12, TEXT, True)
        if i < len(layers) - 1:
            add_line(slide, 2.9, y + 0.69, 2.9, y + 0.93, color=MUTED, width=1.0, end_arrow=True)
    add_code(slide, 'if mode == "smooth_run":\n    remaining = target_steps - abs(position_steps)\n    target_rpm = min(cruise_rpm, braking_rpm(remaining))\nstep_pwm.freq(round(target_rpm * 3200 / 60))', 5.65, 1.55, 6.6, 3.25, CYAN, 15)
    add_box(slide, 5.65, 5.15, 6.6, 0.95, PANEL2, AMBER, radius=True)
    add_text(slide, "Configured ceilings", 5.95, 5.42, 1.8, 0.25, 15, AMBER, True)
    add_text(slide, "1–240 [rev/min]   1–120 [rev/min/s]   15,000 [steps/s]", 7.85, 5.42, 4.0, 0.25, 15, TEXT, True)

    # 16. Peer mode
    slide = new_slide(prs, 16, "Peer coordination", "A filtered, delayed, scaled motion intent travels between the two boards")
    peer_nodes = [
        (0.65, "IMU SAMPLE", "gyro [deg/s]\naccel [m/s²]", CYAN),
        (3.0, "FEATURES", "‖gyro‖ [deg/s]\nadyn [m/s²]", BLUE),
        (5.35, "SCORE", "0.70 gyro +\n0.30 accel [-]", PURPLE),
        (7.7, "FILTER", "EMA τ = 0.18 [s]\nhysteresis [-]", GREEN),
        (10.05, "FOLLOWER", "250 [ms] delay\n0.50 scale [-]", AMBER),
    ]
    for x, label, detail, color in peer_nodes:
        add_flow_node(slide, x, 1.62, 1.8, 1.35, label, detail, color, detail_size=12)
    for x in (2.5, 4.85, 7.2, 9.55):
        add_line(slide, x, 2.3, x + 0.45, 2.3, color=MUTED, width=1.5, end_arrow=True)
    add_code(slide, "gyro_score = clamp(|gyro| / 90 [deg/s], 0, 1)\naccel_score = clamp(adyn / 2.5 [m/s²], 0, 1)\nI_source = 0.70 × gyro_score + 0.30 × accel_score [-]\nI_eff = clamp(3.0 × I_source, 0, 1) × target_fraction [-]\nrpm = 60 × I_eff [rev/min]\namplitude = 0.25 × I_eff [shaft rev]\naccel = min(30, 30 × I_eff) [rev/min/s]", 1.0, 3.55, 6.1, 2.15, PURPLE, 10.5)
    add_box(slide, 7.65, 3.55, 4.65, 1.95, PANEL2, AMBER, radius=True)
    add_text(slide, "SAFETY GATES", 7.95, 3.88, 1.8, 0.25, 15, AMBER, True)
    add_text(slide, "start ≥ 0.18 [-]   stop ≤ 0.10 [-]\nstale timeout = 800 [ms]\nPeer stale/stop detection exists; motor stop delivery is not yet validated.", 7.95, 4.32, 3.9, 0.84, 13, TEXT, True)
    add_text(slide, "Output: I_eff [-] maps to rock command with rpm [rev/min], amplitude [shaft rev], accel [rev/min/s], cycles [-].", 1.05, 5.95, 11.1, 0.32, 15, CYAN, True, PP_ALIGN.CENTER)

    # 17. Validation evidence
    slide = new_slide(prs, 17, "Measured command-path evidence", "Physical log from unloaded-board USB commissioning")
    add_visual(slide, validation, "physical-validation.png", 0.7, 1.45, 7.2, 3.65)
    add_metric(slide, 8.35, 1.55, 2.0, 1.0, "generated target", "160", "steps", CYAN)
    add_metric(slide, 10.65, 1.55, 2.0, 1.0, "USB cmd→idle", "110–113", "ms", AMBER, value_size=17)
    add_metric(slide, 8.35, 2.8, 2.0, 1.0, "generated circle", "±3200", "steps", BLUE)
    add_metric(slide, 10.65, 2.8, 2.0, 1.0, "sensor temp", "31–32", "°C", RED)
    add_box(slide, 0.85, 5.45, 11.5, 0.9, PANEL2, CYAN, radius=True)
    add_text(slide, "KEY READOUT", 1.15, 5.74, 1.55, 0.25, 14, CYAN, True)
    add_text(slide, "4 [rev/min] · 0.05 [shaft rev] → software auto-stop at 160 [steps] → pitch peak 3.06 [deg] · gyro peak 13.73 [deg/s]", 2.95, 5.69, 8.95, 0.3, 14, TEXT, True)
    add_text(slide, "Command path observed: parse → auto-stop → reversal → telemetry → 0.110 [s] stop response.", 1.0, 6.62, 11.25, 0.25, 14, CYAN, True, PP_ALIGN.CENTER)

    # 18. Measurement boundary
    slide = new_slide(prs, 18, "What the current evidence measures", "Separate generated motion, sensed body motion, and physical load")
    add_text(slide, "OBSERVED NOW", 0.85, 1.45, 2.1, 0.25, 15, GREEN, True)
    add_bullets(slide, [
        "Generated position [steps] and travel [shaft rev]",
        "BNO055 orientation [deg], gyro [deg/s], accel [m/s²]",
        "USB stop response [ms]",
        "Unloaded-board temperature [°C]",
    ], 0.9, 1.92, 3.6, 2.55, size=16, spacing=6)
    add_text(slide, "INSTRUMENT NEXT", 4.85, 1.45, 2.4, 0.25, 15, AMBER, True)
    add_bullets(slide, [
        "Physical shaft angle [deg] with marker or encoder",
        "Motor phase current [A] and VMOT [V]",
        "Loaded tilt amplitude [deg] and natural frequency [Hz]",
        "Repeatability [%] and missed-step count [steps]",
    ], 4.9, 1.92, 3.75, 2.55, size=16, spacing=6)
    add_text(slide, "PRODUCT QUESTION", 8.95, 1.45, 2.4, 0.25, 15, PURPLE, True)
    add_bullets(slide, [
        "Can the body hold a target tilt [deg]?",
        "What load [g] and torque [N·m] remain stable?",
        "What temperature rise [°C] occurs over duty time [s]?",
        "Does peer delay [ms] feel intentional?",
    ], 9.0, 1.92, 3.35, 2.55, size=16, spacing=6)
    add_text(slide, "Key gap: commanded shaft motion [steps] versus verified physical shaft motion [deg].", 1.0, 5.42, 11.25, 0.3, 18, CYAN, True, PP_ALIGN.CENTER)
    add_text(slide, "Validated: unloaded USB command path. Not yet validated: loaded tilt, physical shaft angle, torque, power, final gear ratio, or wireless reliability.", 1.0, 5.92, 11.25, 0.42, 13, RED, True, PP_ALIGN.CENTER)

    # 19. Next experiment
    slide = new_slide(prs, 19, "Next experiment", "Close the command-to-motion gap with an instrumented loaded run")
    stages = [
        ("01", "POWER", "VMOT [V]\nlogic [V]", CYAN),
        ("02", "SHAFT", "marker / encoder\nangle [deg]", BLUE),
        ("03", "LOAD", "mass [g]\nCoM offset [mm]", AMBER),
        ("04", "CORRELATE", "tilt [deg]\ncurrent [A]\ntemperature [°C]", GREEN),
    ]
    for i, (number, title, detail, color) in enumerate(stages):
        x = 0.75 + i * 3.1
        add_box(slide, x, 1.72, 2.55, 2.15, PANEL2, color, radius=True)
        add_text(slide, number, x + 0.2, 1.98, 0.45, 0.28, 18, color, True)
        add_text(slide, title, x + 0.75, 1.98, 1.55, 0.25, 16, color, True)
        add_text(slide, detail, x + 0.25, 2.63, 2.05, 0.8, 18, TEXT, True, PP_ALIGN.CENTER)
        if i < len(stages) - 1:
            add_line(slide, x + 2.62, 2.78, x + 2.98, 2.78, color=MUTED, width=1.5, end_arrow=True)
    add_text(slide, "Acceptance output", 1.0, 4.65, 2.1, 0.25, 15, PURPLE, True)
    add_text(slide, "commanded steps [steps] ↔ measured shaft angle [deg] ↔ body response [deg/s, m/s²]", 3.15, 4.62, 8.95, 0.3, 17, TEXT, True)
    add_bullets(slide, [
        "Repeat at conservative speed: 3–10 [rev/min]",
        "Sweep acceleration: 5–30 [rev/min/s]",
        "Record current [A], temperature [°C], tilt [deg], missed steps [steps] over time [s]",
    ], 1.0, 5.35, 10.7, 1.0, size=17, spacing=4)

    # 20. Wireless next steps
    slide = new_slide(prs, 20, "Wireless next steps", "USB works today; Wi-Fi is an experimental HTTP API with unfinished command parity and heartbeat servicing")
    add_text(slide, "CURRENT SETUP", 0.85, 1.45, 2.0, 0.25, 15, CYAN, True)
    add_flow_node(slide, 0.8, 1.95, 2.35, 1.25, "USB SERIAL", "laptop ↔ ESP32\n115200 [bit/s]", CYAN, detail_size=13)
    add_flow_node(slide, 3.65, 1.95, 2.35, 1.25, "JSON", "commands + telemetry\nnewline delimited", BLUE, detail_size=13)
    add_flow_node(slide, 6.5, 1.95, 2.35, 1.25, "DASHBOARD", "controls + plots\nabout 30 [samples/s]", GREEN, detail_size=13)
    add_line(slide, 3.2, 2.58, 3.58, 2.58, color=MUTED, width=1.5, end_arrow=True)
    add_line(slide, 6.05, 2.58, 6.43, 2.58, color=MUTED, width=1.5, end_arrow=True)
    add_text(slide, "WIRELESS PATH", 0.85, 3.85, 2.0, 0.25, 15, PURPLE, True)
    wireless = [
        (0.8, "ACCESS POINT", "2.4 [GHz] Wi-Fi", PURPLE),
        (3.65, "ESP32 HTTP", "GET /api/state\nPOST /api/command", BLUE),
        (6.5, "HEARTBEAT", "750 [ms] watchdog", AMBER),
        (9.35, "PEER RELAY", "motion packet\n250 [ms] delay", GREEN),
    ]
    for x, label, detail, color in wireless:
        add_flow_node(slide, x, 4.35, 2.35, 1.25, label, detail, color, detail_size=12)
    for x in (3.2, 6.05, 8.9):
        add_line(slide, x, 4.98, x + 0.38, 4.98, color=MUTED, width=1.5, end_arrow=True)
    add_box(slide, 0.9, 6.0, 11.45, 0.75, PANEL2, AMBER, radius=True)
    add_text(slide, "STATUS: USB working · Wi-Fi experimental · command parity + heartbeat pending", 1.15, 6.25, 10.95, 0.28, 14, AMBER, True, PP_ALIGN.CENTER)

    # 21. Wiring and peer explanation
    slide = new_slide(prs, 21, "Individual board communication", "First establish one complete board contract; then relay a motion intent to its peer")
    add_text(slide, "INDIVIDUAL BOARD CONTRACT", 0.85, 1.45, 3.4, 0.25, 15, CYAN, True)
    wiring = [
        ("BNO055", "I²C SDA 21 / SCL 22\n100 [kHz]", CYAN),
        ("ESP32", "parses commands\nreads sensor", BLUE),
        ("TMC2209", "STEP 25 / DIR 26 / ENN 27\nVMOT 12 [V]", RED),
        ("STEPPER", "phase current 0.7 [A]\nshaft output", AMBER),
    ]
    for i, (label, detail, color) in enumerate(wiring):
        x = 0.8 + i * 1.62
        add_flow_node(slide, x, 1.95, 1.35, 1.3, label, detail, color, detail_size=10)
        if i < len(wiring) - 1:
            add_line(slide, x + 1.38, 2.6, x + 1.57, 2.6, color=MUTED, width=1.2, end_arrow=True)
    add_text(slide, "BOARD-TO-BOARD INTENT PATH", 0.85, 3.85, 3.7, 0.25, 15, PURPLE, True)
    add_flow_node(slide, 0.8, 4.35, 2.05, 1.25, "EGG A", "telemetry\nfeatures [deg/s, m/s²]", CYAN, detail_size=12)
    add_flow_node(slide, 3.3, 4.35, 2.05, 1.25, "LAPTOP", "filter + sequence\nJSON packet", PURPLE, detail_size=12)
    add_flow_node(slide, 5.8, 4.35, 2.05, 1.25, "DELAY", "250 [ms]\nscale 0.50 [-]", AMBER, detail_size=12)
    add_flow_node(slide, 8.3, 4.35, 2.05, 1.25, "EGG B", "rock intent\nrpm [rev/min]", GREEN, detail_size=12)
    for x in (2.9, 5.4, 7.9):
        add_line(slide, x, 4.98, x + 0.38, 4.98, color=MUTED, width=1.4, end_arrow=True)
    add_text(slide, "STATUS: USB peer path is laptop-mediated; direct board-to-board Wi-Fi is next.", 0.95, 6.22, 11.2, 0.3, 15, CYAN, True, PP_ALIGN.CENTER)

    # 22. Motion design / art and user experience
    slide = new_slide(prs, 22, "Making the wobble feel cute", "Precise control turns mechanical parameters into a motion language")
    add_text(slide, "CUTE IS A CONTROLLED GESTURE", 0.85, 1.45, 5.2, 0.25, 15, PURPLE, True)
    add_text(slide, "parameter → command → measured response → perceived quality", 0.85, 1.72, 5.5, 0.18, 11, MUTED, True)
    cute_inputs = [
        ("amplitude", "size [shaft rev]", "small = contained", CYAN),
        ("rpm", "tempo [rev/min]", "low = gentle", BLUE),
        ("accel", "softness [rev/min/s]", "slow ramp = soft", GREEN),
        ("cycles", "persistence [count]", "brief = expressive", AMBER),
        ("delay", "social timing [ms]", "late reply = character", PURPLE),
        ("intensity", "command scale [-]", "reduced = tender", PINK),
    ]
    for i, (name, unit, meaning, color) in enumerate(cute_inputs):
        y = 1.9 + i * 0.62
        add_text(slide, name, 0.95, y, 1.55, 0.22, 15, color, True)
        add_text(slide, unit, 2.6, y, 1.85, 0.22, 13, MUTED)
        add_text(slide, meaning, 4.5, y, 1.8, 0.22, 14, TEXT, True)
    add_text(slide, "θbody(t) = A · E(t) · sin(2π fw t + φ)", 0.95, 5.55, 5.55, 0.34, 16, CYAN, True)
    add_text(slide, "A [deg]   fw [Hz]   E [-]   t [s]   φ [rad]", 0.95, 5.93, 5.3, 0.22, 12, MUTED, True)
    add_text(slide, "rpm [rev/min] sets motor tempo; fw [Hz] is measured body response.", 0.95, 6.25, 5.55, 0.3, 13, TEXT, True)

    add_text(slide, "AUTHORING FLOW", 7.0, 1.45, 2.2, 0.25, 15, PURPLE, True)
    design_nodes = [
        (7.0, "ANTICIPATE", "low speed\nsmall ramp", CYAN),
        (8.7, "WOBBLE", "bounded tilt\nmeasured [deg]", AMBER),
        (10.4, "SETTLE", "smooth brake\nshort dwell [s]", GREEN),
    ]
    for x, label, detail, color in design_nodes:
        add_flow_node(slide, x, 2.0, 1.45, 1.35, label, detail, color, detail_size=11, label_size=12)
    add_line(slide, 8.48, 2.67, 8.62, 2.67, color=MUTED, width=1.2, end_arrow=True)
    add_line(slide, 10.18, 2.67, 10.32, 2.67, color=MUTED, width=1.2, end_arrow=True)
    add_box(slide, 7.0, 4.05, 4.8, 1.95, PANEL2, RED, radius=True)
    add_text(slide, "ART / USER EXPERIENCE", 7.3, 4.38, 3.0, 0.25, 15, RED, True)
    add_text(slide, "The dashboard authors the gesture.\nThe egg is the visible character.\nA second egg makes it social.\nHypothesis until measured.", 7.3, 4.78, 4.05, 0.9, 13.5, TEXT, True)
    add_text(slide, "Design direction: use variation and delay to make control feel alive.", 7.05, 6.25, 4.8, 0.25, 15, RED, True, PP_ALIGN.CENTER)

    # 23. What I learned
    slide = new_slide(prs, 23, "What I learned", "A first serious hardware build grew out of a software and installation practice")
    add_box(slide, 0.85, 1.5, 5.45, 4.45, PANEL2, PURPLE, radius=True)
    add_text(slide, "STARTING POINT", 1.2, 1.88, 2.0, 0.25, 15, PURPLE, True)
    add_text(slide, "Most of my background is in software, digital and user-experience design, and art installations.", 1.2, 2.35, 4.7, 0.95, 20, TEXT, True)
    add_text(slide, "This project moved that practice into sensing, wiring, motion, and physical feedback.", 1.2, 3.75, 4.7, 0.65, 17, TEXT)
    add_box(slide, 6.95, 1.5, 5.45, 4.45, PANEL2, CYAN, radius=True)
    add_text(slide, "THE HARDWARE LESSON", 7.3, 1.88, 2.8, 0.25, 15, CYAN, True)
    add_text(slide, "This was the first time I soldered since my first year of college.", 7.3, 2.35, 4.65, 0.65, 20, TEXT, True)
    add_text(slide, "I found the work incredibly rewarding and meditative, and I feel very blessed to have had the best mentors.", 7.3, 3.35, 4.7, 1.0, 17, TEXT)
    add_text(slide, "Thank you to the lab for providing tools so generously. I definitely consumed a lot of 3D-printing resources.", 7.3, 4.78, 4.7, 0.72, 16, CYAN, True)
    add_text(slide, "The technical result is a working prototype. The personal result is a wider practice.", 1.1, 6.35, 11.0, 0.3, 18, RED, True, PP_ALIGN.CENTER)

    # 24. Photo placeholder page
    slide = new_slide(prs, 24, "Photos and meals", "Space for process documentation and the shared studio life around the build")
    placeholders = [
        (0.8, 1.55, 5.7, 2.05, "FIRST SOLDERING / PROCESS"),
        (6.85, 1.55, 5.7, 2.05, "WIRING + DEBUGGING"),
        (0.8, 4.05, 5.7, 2.05, "3D PRINT ITERATIONS / RESOURCES"),
        (6.85, 4.05, 5.7, 2.05, "MEALS / MENTORSHIP"),
    ]
    for x, y, w, h, label in placeholders:
        add_box(slide, x, y, w, h, BG, MUTED, radius=False)
        add_text(slide, label, x + 0.25, y + h / 2 - 0.15, w - 0.5, 0.3, 15, MUTED, True, PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # 25. Source map
    slide = new_slide(prs, 25, "Reproducibility", "Source map for the deck, video, and prototype")
    add_box(slide, 0.9, 1.55, 11.5, 4.85, PANEL2, CYAN, radius=True)
    add_text(slide, "BUILD", 1.25, 1.92, 1.2, 0.25, 15, CYAN, True)
    add_code(slide, "python3 simulator/docs/build_google_slides_deck.py\n# output: simulator/docs/WOBBLE_MECHANISMS_TECHNICAL_DECK_post_critique.pptx", 1.25, 2.3, 10.8, 0.95, CYAN, 14)
    add_text(slide, "PRIMARY REFERENCES", 1.25, 3.65, 2.6, 0.25, 15, AMBER, True)
    add_text(slide, "simulator/docs/TECHNICAL_PRESENTATION.md\nsimulator/docs/PHYSICS_TALKING_OUTLINE.md\nsimulator/docs/CAD_IMPORT_GUIDE.md\nsimulator/src/egg_model.py\nsimulator/wired_tests/physical_test_log.md\nsimulator/firmware/main.py\nsimulator/dashboard/index.html\nsimulator/dual_board/ripple_logic.py", 1.25, 4.05, 5.75, 1.95, 12.7, TEXT, font="Menlo", spacing=0)
    add_text(slide, "RASTER ASSETS", 7.25, 3.65, 2.0, 0.25, 15, GREEN, True)
    add_text(slide, "simulator/docs/assets/png/\nsystem-architecture.png\nphysical-validation.png\negg-unit-sheet1-schematic-focus.png", 7.25, 4.05, 4.9, 1.15, 13, TEXT, font="Menlo", spacing=2)
    add_text(slide, "COMPANION VIDEO", 7.25, 5.45, 2.2, 0.25, 15, GREEN, True)
    add_text(slide, "simulator/ripple_3d/output/\nripple_4x4.mp4", 7.25, 5.78, 4.9, 0.45, 12, TEXT, font="Menlo", spacing=1)
    add_text(slide, "Explanatory only: not calibrated rigid-body dynamics.", 7.25, 6.18, 4.9, 0.2, 10.5, MUTED, True)
    add_text(slide, "Technical flow: model → command → pulse → motion → measurement.", 1.2, 6.72, 10.9, 0.25, 17, RED, True, PP_ALIGN.CENTER)

    # 26. Mechanical design / load path
    slide = new_slide(prs, 26, "Mechanical design: load path + center of mass", "Mass properties, bearing support, and contact geometry determine how torque becomes visible wobble")
    add_box(slide, 0.75, 1.45, 5.8, 4.82, PANEL2, BLUE, radius=True)
    add_text(slide, "MECHANICAL LOAD PATH", 1.05, 1.78, 2.8, 0.25, 15, BLUE, True)
    add_flow_node(slide, 1.0, 2.18, 1.45, 0.68, "MOTOR / SHAFT", "τmotor [N·m]", RED, detail_size=10, label_size=11)
    add_flow_node(slide, 2.82, 2.18, 1.65, 0.68, "BEARING SUPPORT", "radial + axial load [N]", AMBER, detail_size=9.5, label_size=10.5)
    add_flow_node(slide, 4.88, 2.18, 1.28, 0.68, "OFFSET MASS", "r [m]", PURPLE, detail_size=10, label_size=10.5)
    add_line(slide, 2.52, 2.52, 2.76, 2.52, color=MUTED, width=1.2, end_arrow=True)
    add_line(slide, 4.54, 2.52, 4.82, 2.52, color=MUTED, width=1.2, end_arrow=True)

    egg = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(2.18), Inches(3.02), Inches(2.32), Inches(2.62))
    egg.fill.solid()
    egg.fill.fore_color.rgb = RGBColor(238, 226, 190)
    egg.line.color.rgb = AMBER
    egg.line.width = Pt(1.4)
    add_box(slide, 2.58, 3.55, 1.52, 0.32, RED, RED, radius=True)
    add_text(slide, "internal mechanism", 2.62, 3.92, 1.05, 0.22, 9.2, TEXT, True, PP_ALIGN.CENTER)
    add_box(slide, 3.0, 4.78, 0.68, 0.45, AMBER, AMBER, radius=True)
    add_text(slide, "CoM", 3.06, 4.88, 0.56, 0.16, 10, BG, True, PP_ALIGN.CENTER)
    add_box(slide, 3.25, 4.05, 0.16, 0.16, RED, RED, radius=True)
    add_text(slide, "geom.\ncenter", 3.7, 3.92, 0.62, 0.42, 9.5, MUTED, True, PP_ALIGN.CENTER)
    add_line(slide, 3.33, 4.16, 3.33, 4.75, color=AMBER, width=1.2, end_arrow=True)
    add_text(slide, "dCoM = 25 [mm]", 3.62, 4.48, 1.05, 0.38, 10.5, AMBER, True)
    add_box(slide, 3.03, 5.45, 0.62, 0.22, BLUE, BLUE, radius=True)
    add_text(slide, "contact", 2.86, 5.82, 0.95, 0.2, 11, MUTED, True, PP_ALIGN.CENTER)
    add_line(slide, 3.34, 5.47, 3.34, 5.25, color=BLUE, width=1.2, end_arrow=True)
    add_text(slide, "load returns through shell → contact → table", 1.02, 6.05, 5.2, 0.25, 13, TEXT, True, PP_ALIGN.CENTER)

    add_box(slide, 6.85, 1.45, 5.7, 2.25, PANEL2, CYAN, radius=True)
    add_text(slide, "MODEL INPUTS / REPOSITORY", 7.15, 1.78, 5.0, 0.25, 14.5, CYAN, True)
    add_text(slide, "mass m = 500 [g] = 0.500 [kg]\nsemi-axes ≈ 35 × 35 × 40 [mm]\nCoM = (0, 0, −25) [mm] from geometric center\ncontact radius = 35 [mm] · roughness = 0.1 [mm]\nshell thickness = 2 [mm]", 7.15, 2.18, 5.05, 1.18, 14, TEXT, True, spacing=1)

    add_box(slide, 6.85, 3.95, 5.7, 2.08, PANEL2, AMBER, radius=True)
    add_text(slide, "TORQUE CALCULATION", 7.15, 4.28, 2.85, 0.25, 15, AMBER, True)
    add_text(slide, "τg = −m g ℓCoM sin(θ)\nθrad = θdeg × π / 180\nkg ≈ m g ℓCoM  [N·m/rad]", 7.15, 4.68, 2.85, 0.95, 15.5, TEXT, True, spacing=2)
    add_text(slide, "Proxy: m g dCoM = 0.123 [N·m/rad].\nUse dCoM for the model; ℓCoM is contact-to-CoM. Measure contact geometry before treating the proxy as physical torque.", 10.05, 4.66, 2.25, 1.18, 10.5, TEXT, True, spacing=1)

    add_box(slide, 6.85, 6.22, 5.7, 0.55, PANEL2, RED, radius=True)
    add_text(slide, "BEARING / LOAD CHECK NEXT: load [N] · support spacing [mm] · backlash [deg] · drag [N·m]", 7.05, 6.39, 5.3, 0.2, 11.5, RED, True, PP_ALIGN.CENTER)

    # Reorder the authored sections into the presentation story: hardware →
    # components → mechanics → physics → individual board → peer → code layers
    # → runtime → wireless → controls → evidence → art.
    reorder_slides(prs, [
        1, 2, 7, 6, 26, 3, 4, 5, 21, 16, 8, 9, 20, 10, 11, 12, 13, 14,
        15, 17, 18, 19, 22, 23, 24, 25,
    ])

    output.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Wobble Mechanisms technical deck")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    build(args.output)
