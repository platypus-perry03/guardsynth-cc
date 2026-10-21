"""Check duration boundaries and spatial interpretation of the hold measurement."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

PATH = Path(__file__).resolve().parents[1] / 'experiments/paper1_external_methods/run_position_hold.py'
SPEC = importlib.util.spec_from_file_location('position_hold', PATH)
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class PositionHoldTests(unittest.TestCase):
    def test_case_reuses_canonical_input_and_keeps_older_manifests_readable(self):
        folder = Path('/tmp/position-hold-test-001')
        relative = 'projects/04-guardsynth-coc/artifacts/restricted/example/input.pt'
        self.assertEqual(R.input_path({'input_path': relative}, folder), R.ROOT / relative)
        self.assertEqual(R.input_path({}, folder), folder / 'inputs.pt')

    def test_motion_after_short_hold_is_allowed_but_during_long_hold_is_rejected(self):
        xyz = np.zeros((64, 3))
        xyz[5:, 0] = 1.
        self.assertFalse(R.trajectory_metrics(xyz, [0, 0, 0], .5)['exceeds_with_0_01_m_tolerance'])
        self.assertTrue(R.trajectory_metrics(xyz, [0, 0, 0], 2.)['exceeds_with_0_01_m_tolerance'])
        self.assertAlmostEqual(R.trajectory_metrics(xyz, [0, 0, 0], .5)['first_departure_sample_s'], .6)

    def test_endpoint_is_checked_even_if_the_vehicle_later_returns(self):
        xyz = np.zeros((64, 3))
        xyz[4, 0] = .22
        self.assertTrue(R.trajectory_metrics(xyz, [0, 0, 0], .5)['exceeds_with_0_01_m_tolerance'])

    def test_xy_origin_and_inclusive_radius(self):
        xyz = np.tile([3., 4.2, 99.], (64, 1))
        result = R.trajectory_metrics(xyz, [3., 4., 1.], 2.)
        self.assertAlmostEqual(result['maximum_displacement_during_hold_m'], .2)
        self.assertFalse(result['exceeds_with_0_01_m_tolerance'])
        self.assertIsNone(result['first_departure_sample_s'])


if __name__ == '__main__':
    unittest.main()
