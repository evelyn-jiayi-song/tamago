"""Focused tests for the balanced-still weight coordinate model."""

import unittest

from coordinate_system import WeightCoordinateSystem, wrap_degrees


class CoordinateSystemTests(unittest.TestCase):
    def test_heading_wraps_across_zero(self):
        self.assertEqual(wrap_degrees(181), -179)
        self.assertEqual(wrap_degrees(-181), 179)

    def test_balanced_still_is_zero(self):
        coordinates = WeightCoordinateSystem(steps_per_rev=3200)
        imu = {"heading": 238.125, "roll": -85.688, "pitch": -2.375}
        motor = {"position_steps": 0}
        coordinates.set_reference(imu, motor)
        self.assertEqual(coordinates.update(imu, motor)["tilt_magnitude_deg"], 0.0)

    def test_motor_quarter_turn_maps_to_quarter_phase(self):
        coordinates = WeightCoordinateSystem(steps_per_rev=3200, arm_radius_mm=100)
        imu = {"heading": 0, "roll": 0, "pitch": 0}
        coordinates.set_reference(imu, {"position_steps": 0})
        result = coordinates.update(imu, {"position_steps": 800})
        self.assertEqual(result["shaft_deg"], 90.0)
        self.assertEqual(result["weight_xy_mm"], {"x": 0.0, "y": 100.0, "z": 0.0})


if __name__ == "__main__":
    unittest.main()
