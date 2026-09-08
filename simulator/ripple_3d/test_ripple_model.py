import unittest

from ripple_model import RippleSimulation


class RippleModelTests(unittest.TestCase):
    def setUp(self):
        self.sim = RippleSimulation(size=5, propagation_speed=2.0,
                                    damping=0.5, wobble_duration_ms=400)

    def test_grid_neighbors(self):
        self.assertEqual(len(self.sim.neighbors(2, 2)), 4)
        self.assertEqual(len(self.sim.neighbors(0, 0)), 2)
        self.assertEqual(self.sim.neighbors(2, 2), [(1, 2), (2, 3), (3, 2), (2, 1)])

    def test_central_push_is_immediate_and_reaches_neighbors_later(self):
        self.sim.push(2, 2, strength=1.0, now_ms=100)
        self.sim.advance(100)
        center = self.sim.snapshot()[self.sim.index(2, 2)]
        neighbor = self.sim.snapshot()[self.sim.index(2, 3)]
        self.assertTrue(center["active"])
        self.assertAlmostEqual(center["amplitude"], 1.0)
        self.assertFalse(neighbor["active"])
        self.sim.advance(600)
        neighbor = self.sim.snapshot()[self.sim.index(2, 3)]
        self.assertTrue(neighbor["active"])
        self.assertAlmostEqual(neighbor["amplitude"], 0.5)

    def test_distance_timing_and_damping(self):
        self.sim.push(2, 2, strength=0.8, now_ms=0)
        self.sim.advance(1000)
        far_corner = self.sim.snapshot()[self.sim.index(0, 0)]
        self.assertFalse(far_corner["active"])
        self.assertAlmostEqual(far_corner["amplitude"], 0.0)
        self.sim.advance(2000)
        far_corner = self.sim.snapshot()[self.sim.index(0, 0)]
        self.assertTrue(far_corner["active"])
        self.assertAlmostEqual(far_corner["started_ms"], 2000)
        self.assertAlmostEqual(far_corner["amplitude"], 0.8 * (0.5 ** 4))

    def test_reset_clears_pending_and_applied_motion(self):
        self.sim.push(2, 2, strength=1.0)
        self.sim.advance(0)
        self.sim.reset()
        self.assertEqual(self.sim.time_ms, 0.0)
        self.assertTrue(all(not egg["active"] for egg in self.sim.snapshot()))
        self.assertTrue(all(egg["push_count"] == 0 for egg in self.sim.snapshot()))


if __name__ == "__main__":
    unittest.main()
