#!/usr/bin/env python3
"""Plot previously captured physical characterization JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("results/physical-validation"))
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("physical_*.json"))
    runs = []
    for path in files:
        data = json.loads(path.read_text())
        for run in data.get("runs", []):
            observed = run.get("observed", {})
            runs.append({
                "name": run.get("name", path.stem),
                "pitch": observed.get("pitch", {}).get("peak_abs", 0),
                "roll": observed.get("roll", {}).get("peak_abs", 0),
                "heading": observed.get("heading", {}).get("peak_abs", 0),
                "gyro": observed.get("gyro_vector_dps", {}).get("peak_abs", 0),
                "temperature": observed.get("temperature_c", {}).get("max", 0),
            })
    if not runs:
        raise SystemExit("no physical_*.json files found")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    names = [run["name"] for run in runs]
    x = range(len(runs))
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    width = 0.2
    axes[0].bar([i - width for i in x], [r["pitch"] for r in runs],
                width, label="pitch peak (deg)")
    axes[0].bar(x, [r["roll"] for r in runs], width, label="roll peak (deg)")
    axes[0].bar([i + width for i in x], [r["heading"] for r in runs],
                width, label="heading peak (deg)")
    axes[0].set_ylabel("angle (deg)")
    axes[0].set_title("Physical wobble-angle characterization")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(x, [r["gyro"] for r in runs], color="#f4a261",
                label="gyro vector peak (dps)")
    axes[1].set_ylabel("gyro (dps)")
    axes[1].set_title("IMU motion response")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend()
    axes[1].set_xticks(list(x), names, rotation=35, ha="right")
    fig.tight_layout()
    fig.savefig(args.output_dir / "physical-validation.png", dpi=200)
    (args.output_dir / "summary.json").write_text(
        json.dumps({"runs": runs}, indent=2) + "\n"
    )
    print("saved", args.output_dir / "physical-validation.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
