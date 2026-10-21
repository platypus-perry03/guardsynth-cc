"""Analytical checks of trajectory speed and inclusive limit boundaries."""
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/paper1_external_methods'))
from run_alpamayo_speed_limits import trajectory_metrics


class SpeedLimitMeasurements(unittest.TestCase):
    def test_first_interval_uses_supplied_origin_and_height_is_excluded(self):
        origin = np.array([7., 4., 100.])
        times = np.arange(1, 65) * .1
        trajectory = origin + times[:, None] * np.array([3., 4., 20.])
        result = trajectory_metrics(trajectory, origin, 5.)
        np.testing.assert_allclose(result['segment_average_speed_mps'], 5., atol=1e-12)
        self.assertFalse(result['windows']['6.4']['exceeds_with_0_05_mps_tolerance'])

    def test_late_exceedance_does_not_contaminate_shorter_windows(self):
        speeds = np.full(64, 2.)
        speeds[30] = 2.1
        trajectory = np.column_stack([np.cumsum(speeds * .1), np.zeros(64), np.zeros(64)])
        result = trajectory_metrics(trajectory, np.zeros(3), 2.)
        self.assertFalse(result['windows']['2.0']['exceeds_with_0_05_mps_tolerance'])
        self.assertTrue(result['windows']['6.4']['exceeds_with_0_05_mps_tolerance'])
        self.assertAlmostEqual(result['windows']['6.4']['max_excess_mps'], .1)

    def test_stationary_is_allowed_by_both_limits(self):
        for limit in (.9, 9.9):
            result = trajectory_metrics(np.zeros((64, 3)), np.zeros(3), limit)
            self.assertEqual(result['windows']['6.4']['max_excess_mps'], 0)
            self.assertEqual(result['windows']['6.4']['strict_exceedance_intervals'], 0)


if __name__ == '__main__':
    unittest.main()
