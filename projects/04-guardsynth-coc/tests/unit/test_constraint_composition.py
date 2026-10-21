"""Checks for the guardsynth-coc composition experiment's scientific controls."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'PROJECT_REGISTRY.json').exists())
sys.path.insert(0, str(ROOT / 'projects/04-guardsynth-coc/experiments/paper1_cnl_learning'))
import constraint_composition as experiment


class CompositionControls(unittest.TestCase):
    def test_pairwise_checks_miss_a_three_way_conflict(self):
        case = experiment.build_case('three_way_timing', dict(wait_ms=500, delay_ms=100, deadline_ms=599))
        case['id'] = 'three-way-control'
        result = experiment.evaluate(case)
        self.assertTrue(result['components_sat'])
        self.assertTrue(result['pairs_sat'])
        self.assertEqual(result['full_status'], 'UNSAT')
        self.assertEqual(result['minimal_conflict_groups'], [['release_wait', 'transition_delay', 'entry_deadline']])
        self.assertEqual(len({c['source_refs'][0] for c in case['constraints']}), 3)
        self.assertEqual(case['constraints'][1]['source_kind'], 'SUPPLIED_SYNTHETIC_MODELING_ASSUMPTION')

    def test_optional_entry_does_not_create_a_false_conflict(self):
        params = dict(clear_ms=2000, wait_ms=500, deadline_ms=2499, required_entry=True)
        for required, status in [(True, 'UNSAT'), (False, 'SAT')]:
            params['required_entry'] = required
            case = experiment.build_case('entry_deadline', dict(params))
            case['id'] = 'entry-obligation-control'
            result = experiment.evaluate(case)
            self.assertEqual(result['full_status'], status)
            if not required:
                self.assertFalse(result['queries'][-1]['witness']['enters'])

    def test_hold_endpoint_is_inclusive_and_release_is_effective(self):
        for sample, distance, status in [(500, 201, 'UNSAT'), (500, 200, 'SAT'), (1000, 201, 'SAT')]:
            case = experiment.build_case('hold_departure', dict(hold_ms=500, departure_sample_ms=sample, required_x_mm=distance))
            case['id'] = 'hold-boundary-control'
            self.assertEqual(experiment.evaluate(case)['full_status'], status)

    def test_independent_witness_check_rejects_an_overspeed_assignment(self):
        case = experiment.build_case('speed_progress', dict(cap_mm_s=500, horizon_s=2, minimum_mm=1000))
        case['id'] = 'speed-witness-control'
        result = experiment.evaluate(case)
        query = result['queries'][-1]
        self.assertTrue(query['witness_valid'])
        bad = deepcopy(query['witness'])
        bad['speed_mm_s'], bad['distance_mm'] = 501, 1002
        self.assertFalse(experiment.valid_witness(case, (0, 1), bad))


if __name__ == '__main__':
    unittest.main()
