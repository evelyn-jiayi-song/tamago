"""Focused host tests for the isolated ripple protocol."""

import unittest

from simulator.dual_board.ripple_logic import (
    FollowerController,
    MotionIntensityFilter,
    ReferencePublisher,
)


STILL = {
    "gyro": {"x": 0, "y": 0, "z": 0},
    "accel": {"x": 0, "y": 0, "z": 9.80665},
}
MOVING = {
    "gyro": {"x": 0, "y": 0, "z": 45},
    "accel": {"x": 0, "y": 0, "z": 9.80665},
}


class RippleLogicTests(unittest.TestCase):
    def test_still_pose_has_zero_motion_score(self):
        result = MotionIntensityFilter().update(STILL, 0.05)
        self.assertEqual(result["raw"], 0.0)
        self.assertEqual(result["intensity"], 0.0)
        self.assertFalse(result["active"])

    def test_filter_requires_warmup_and_hysteresis_stops(self):
        motion_filter = MotionIntensityFilter()
        active = False
        for _ in range(12):
            active = motion_filter.update(MOVING, 0.05)["active"]
        self.assertTrue(active)
        for _ in range(30):
            result = motion_filter.update(STILL, 0.05)
        self.assertFalse(result["active"])
        self.assertLess(result["intensity"], 0.10)

    def test_publisher_schema_and_period_limit(self):
        publisher = ReferencePublisher()
        self.assertEqual(publisher.update(STILL, 0)["kind"], "stop")
        self.assertIsNone(publisher.update(STILL, 10))
        packet = None
        for now_ms in range(50, 650, 50):
            candidate = publisher.update(MOVING, now_ms)
            if candidate and candidate["kind"] == "motion":
                packet = candidate
                break
        self.assertIsNotNone(packet)
        self.assertEqual(set(("v", "kind", "source", "seq", "t_ms",
                              "intensity", "active", "axis", "features")),
                         set(packet))
        self.assertGreaterEqual(packet["intensity"], 0.0)
        self.assertLessEqual(packet["intensity"], 1.0)

    def test_follower_applies_delay_and_half_intensity(self):
        packet = {
            "v": 1, "kind": "motion", "source": "A", "seq": 7,
            "t_ms": 0, "intensity": 0.8, "active": True, "axis": "tilt",
            "features": {"gyro_dps": 40, "dynamic_accel_mps2": 0.1},
        }
        follower = FollowerController(delay_ms=250, target_fraction=0.5)
        self.assertTrue(follower.receive(packet, 100))
        self.assertIsNone(follower.tick(349))
        command = follower.tick(350)
        self.assertEqual(command["cmd"], "rock")
        self.assertAlmostEqual(command["intensity"], 0.4)
        self.assertAlmostEqual(command["rpm"], 24.0)

    def test_stop_packet_is_delayed_and_stale_timeout_is_safe(self):
        follower = FollowerController(delay_ms=100, stale_timeout_ms=400)
        motion = {
            "v": 1, "kind": "motion", "source": "A", "seq": 1,
            "t_ms": 0, "intensity": 1.0, "active": True, "axis": "tilt",
        }
        stop = dict(motion, kind="stop", seq=2, intensity=0.0, active=False)
        follower.receive(motion, 0)
        self.assertEqual(follower.tick(100)["cmd"], "rock")
        follower.receive(stop, 150)
        self.assertIsNone(follower.tick(249))
        self.assertEqual(follower.tick(250)["reason"], "peer_stop")
        follower = FollowerController(delay_ms=0, stale_timeout_ms=400)
        follower.receive(motion, 0)
        follower.tick(0)
        self.assertEqual(follower.tick(401)["reason"], "peer_stale")

    def test_rejects_wrong_source_old_sequence_and_bad_version(self):
        follower = FollowerController()
        base = {"v": 1, "kind": "motion", "source": "A", "seq": 3,
                "t_ms": 0, "intensity": 0.5, "active": True}
        self.assertTrue(follower.receive(base, 0))
        self.assertFalse(follower.receive(dict(base, seq=2), 1))
        self.assertFalse(follower.receive(dict(base, source="B", seq=4), 2))
        self.assertFalse(follower.receive(dict(base, v=2, seq=4), 3))


if __name__ == "__main__":
    unittest.main()

