"""Scientific controls for manually document-grounded composition cases."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'PROJECT_REGISTRY.json').exists())
sys.path.insert(0, str(ROOT / 'projects/04-guardsynth-coc/experiments/paper1_cnl_learning'))
import document_grounded_composition as experiment


def solve(family, **parameters):
    case = experiment.build_case(family, parameters)
    case['id'] = 'scientific-control'
    result = experiment.evaluate(case)
    assert all(q['matches_expected'] and q['witness_valid'] is not False for q in result['queries'])
    return case, result


class DocumentGroundedControls(unittest.TestCase):
    def test_suppression_conflict_is_three_way_and_delay_removal_repairs_it(self):
        # Hypothetical state: immediate stopping needs 10 m; delayed stopping needs 20 m.
        p = dict(speed_m_s=10, deceleration_m_s2=5, obstacle_mm=15000, delay_ms=1000)
        _, result = solve('suppression', **p)
        self.assertEqual(result['full_status'], 'UNSAT')
        self.assertTrue(result['pairs_sat'])
        self.assertEqual(result['minimal_conflict_groups'], [['suppression', 'braking_model', 'avoidance_goal']])
        p['delay_ms'] = 0
        self.assertEqual(solve('suppression', **p)[1]['full_status'], 'SAT')

    def test_already_impossible_avoidance_is_not_attributed_to_suppression(self):
        _, result = solve('suppression', speed_m_s=10, deceleration_m_s2=5, obstacle_mm=9000, delay_ms=1000)
        self.assertEqual(result['minimal_conflict_groups'], [['braking_model', 'avoidance_goal']])
        self.assertFalse(result['pairs_sat'])

    def test_yellow_dilemma_and_longer_interval_control(self):
        p = dict(speed_m_s=15, deceleration_m_s2=3, reaction_ms=1000, yellow_ms=3000, distance_mm=50000)
        _, result = solve('yellow', **p)
        self.assertTrue(result['components_sat'])
        self.assertEqual(result['full_status'], 'UNSAT')
        p['yellow_ms'] = 4000
        self.assertEqual(solve('yellow', **p)[1]['full_status'], 'SAT')

    def test_interlock_is_about_autonomous_driving_and_hold_remains_feasible(self):
        p = dict(door=True, park=False, parking_brake=False, airbag=False, drive=True)
        case, result = solve('interlock', **p)
        self.assertEqual(result['full_status'], 'UNSAT')
        self.assertNotIn('vehicle_motion', {d['name'] for d in case['context_model']['declarations']})
        p['drive'] = False
        self.assertEqual(solve('interlock', **p)[1]['full_status'], 'SAT')

    def test_permission_is_not_a_crossing_obligation(self):
        p = dict(stationary=True, necessary=True, clear=True, cross=True, faithful=True)
        self.assertEqual(solve('exception', **p)[1]['full_status'], 'SAT')
        p['faithful'] = False
        self.assertEqual(solve('exception', **p)[1]['full_status'], 'UNSAT')
        p['cross'] = False
        self.assertEqual(solve('exception', **p)[1]['full_status'], 'SAT')
        p.update(faithful=True, clear=False, cross=True)
        self.assertEqual(solve('exception', **p)[1]['full_status'], 'UNSAT')

    def test_witness_check_rejects_nominal_stop_without_enough_distance(self):
        case, result = solve('yellow', speed_m_s=15, deceleration_m_s2=3,
                             reaction_ms=1000, yellow_ms=4000, distance_mm=50000)
        good = result['queries'][-1]['witness']
        self.assertTrue(experiment.valid_witness(case, (0, 1), good))
        bad = deepcopy(good)
        bad['stop'] = True
        self.assertFalse(experiment.valid_witness(case, (0, 1), bad))


if __name__ == '__main__':
    unittest.main()
