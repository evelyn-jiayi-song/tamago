"""Focused host tests for the isolated ripple protocol."""

import unittest

from simulator.dual_board.ripple_logic import (
    FollowerController,
    MotionIntensityFilter,
    PeerEchoGate,
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
                              "intensity", "active", "axis",
                              "features")),
                         set(packet))
        self.assertGreaterEqual(packet["intensity"], 0.0)
        self.assertLessEqual(packet["intensity"], 1.0)

    def test_follower_applies_delay_and_boosted_half_intensity(self):
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
        self.assertAlmostEqual(command["intensity"], 0.75)
        self.assertAlmostEqual(command["rpm"], 112.5)
        self.assertAlmostEqual(command["accel"], 56.25)
        self.assertAlmostEqual(command["amplitude_rev"], 2.25)
        self.assertEqual(command["cycles"], 2)

    def test_follower_response_gain_is_capped_by_target_fraction(self):
        packet = {
            "v": 1, "kind": "motion", "source": "A", "seq": 8,
            "t_ms": 0, "intensity": 0.3, "active": True, "axis": "tilt",
        }
        follower = FollowerController(delay_ms=0, target_fraction=0.5)
        self.assertTrue(follower.receive(packet, 0))
        command = follower.tick(0)
        self.assertAlmostEqual(command["intensity"], 0.675)
        self.assertAlmostEqual(command["rpm"], 101.25)
        self.assertAlmostEqual(command["accel"], 50.625)
        self.assertAlmostEqual(command["amplitude_rev"], 2.025)

    def test_stop_packet_and_stale_timeout_issue_one_shot_motor_stop(self):
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
        stop_command = follower.tick(250)
        self.assertEqual(stop_command["cmd"], "stop")
        self.assertIsNone(follower.tick(251))
        follower.receive(dict(stop, seq=3), 251)
        self.assertIsNone(follower.tick(351))
        follower = FollowerController(delay_ms=0, stale_timeout_ms=400)
        follower.receive(motion, 0)
        self.assertEqual(follower.tick(0)["cmd"], "rock")
        self.assertEqual(follower.tick(401)["cmd"], "stop")
        self.assertIsNone(follower.tick(402))

    def test_echo_gate_suppresses_peer_response_then_reopens_after_cooldown(self):
        gate = PeerEchoGate(reaction_hold_ms=100, stop_cooldown_ms=25)
        gate.trigger(1000, {"cmd": "rock"})
        self.assertTrue(gate.is_suppressed(1099))
        self.assertFalse(gate.is_suppressed(1100))
        gate.trigger(1100, {"cmd": "stop"})
        self.assertTrue(gate.is_suppressed(1124))
        self.assertFalse(gate.is_suppressed(1125))

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
