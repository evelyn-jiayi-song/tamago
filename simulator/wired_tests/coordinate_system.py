"""Relative coordinate model for the moving weight.

The BNO055 reports orientation, not absolute position.  This model therefore
uses two complementary coordinates:

* ``shaft_deg`` / ``shaft_rev``: commanded motor phase from TMC step counts.
* ``heading_deg``, ``roll_deg``, and ``pitch_deg``: IMU angles relative to a
  recorded balanced/still reference pose.

An optional arm radius converts shaft phase into an XY point in the mechanism
plane.  The XY result is a kinematic estimate; it is not a measurement of
translation from the BNO055.
"""

from __future__ import annotations

import math


def wrap_degrees(value: float) -> float:
    """Return an angle in the half-open interval [-180, 180)."""
    return (float(value) + 180.0) % 360.0 - 180.0


class WeightCoordinateSystem:
    """Track the moving weight relative to a balanced, still pose."""

    def __init__(self, steps_per_rev: int = 3200, arm_radius_mm: float | None = None):
        if steps_per_rev <= 0:
            raise ValueError("steps_per_rev must be positive")
        if arm_radius_mm is not None and arm_radius_mm <= 0:
            raise ValueError("arm_radius_mm must be positive when provided")
        self.steps_per_rev = int(steps_per_rev)
        self.arm_radius_mm = arm_radius_mm
        self.reference = None

    def set_reference(self, imu: dict, motor: dict | None = None) -> dict:
        """Record the current balanced/still pose as coordinate zero."""
        motor = motor or {}
        self.reference = {
            "heading": float(imu.get("heading", 0.0)),
            "roll": float(imu.get("roll", 0.0)),
            "pitch": float(imu.get("pitch", 0.0)),
            "position_steps": int(motor.get("position_steps", 0) or 0),
        }
        return dict(self.reference)

    def update(self, imu: dict, motor: dict | None = None) -> dict:
        """Return the current relative pose and optional kinematic XY point."""
        if self.reference is None:
            raise RuntimeError("set_reference must be called while the weight is balanced")

        motor = motor or {}
        position_steps = int(motor.get("position_steps", 0) or 0)
        relative_steps = position_steps - self.reference["position_steps"]
        shaft_rev = relative_steps / float(self.steps_per_rev)
        shaft_deg = (shaft_rev * 360.0) % 360.0

        heading_deg = wrap_degrees(float(imu.get("heading", 0.0)) - self.reference["heading"])
        roll_deg = float(imu.get("roll", 0.0)) - self.reference["roll"]
        pitch_deg = float(imu.get("pitch", 0.0)) - self.reference["pitch"]
        tilt_deg = math.sqrt(roll_deg * roll_deg + pitch_deg * pitch_deg)

        coordinate = {
            "shaft_deg": round(shaft_deg, 3),
            "shaft_rev": round(shaft_rev, 6),
            "heading_deg": round(heading_deg, 3),
            "roll_deg": round(roll_deg, 3),
            "pitch_deg": round(pitch_deg, 3),
            "tilt_magnitude_deg": round(tilt_deg, 3),
            "reference": "balanced_still",
        }
        if self.arm_radius_mm is not None:
            theta = math.radians(shaft_deg)
            coordinate["weight_xy_mm"] = {
                "x": round(self.arm_radius_mm * math.cos(theta), 3),
                "y": round(self.arm_radius_mm * math.sin(theta), 3),
                "z": 0.0,
            }
        return coordinate
