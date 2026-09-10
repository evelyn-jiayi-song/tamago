#!/usr/bin/env python3
"""Generate publication-ready plots from capture_session.py output."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    output_dir = args.output_dir or args.input.with_suffix("")
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = data.get("samples", [])
    boards = data.get("boards", sorted({s["board"] for s in samples}))
    colors = {"egg-a": "#087e8b", "egg-b": "#f4a261"}

    with (output_dir / "samples.csv").open("w", newline="") as handle:
        if samples:
            writer = csv.DictWriter(handle, fieldnames=samples[0].keys())
            writer.writeheader()
            writer.writerows(samples)

    figures = [
        ("angles.png", "Wobble angle", ("roll", "pitch"), "degrees"),
        ("speed-position.png", "Motor profile", ("rpm", "distance_rev"),
         "RPM / revolutions"),
        ("imu-motion.png", "IMU motion", ("gyro_magnitude", "dynamic_accel"),
         "dps / m/s²"),
    ]
    for filename, title, fields, ylabel in figures:
        fig, axes = plt.subplots(len(fields), 1, figsize=(11, 7), sharex=True)
        if len(fields) == 1:
            axes = [axes]
        for axis, field in zip(axes, fields):
            for board in boards:
                rows = [row for row in samples if row["board"] == board]
                x = [row["t_s"] for row in rows]
                if field == "gyro_magnitude":
                    y = [((float(row.get("gyro_x") or 0) ** 2 +
                           float(row.get("gyro_y") or 0) ** 2 +
                           float(row.get("gyro_z") or 0) ** 2) ** 0.5)
                         for row in rows]
                elif field == "dynamic_accel":
                    y = [abs(((float(row.get("accel_x") or 0) ** 2 +
                               float(row.get("accel_y") or 0) ** 2 +
                               float(row.get("accel_z") or 0) ** 2) ** 0.5)
                             - 9.80665) for row in rows]
                else:
                    y = [row.get(field) for row in rows]
                axis.plot(x, y, label=board, color=colors.get(board))
            axis.set_ylabel(field.replace("_", " "))
            axis.grid(alpha=0.25)
            axis.legend(loc="upper right")
        axes[-1].set_xlabel("time (s)")
        fig.suptitle(title)
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=180)
        plt.close(fig)
    print("saved plots in", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
