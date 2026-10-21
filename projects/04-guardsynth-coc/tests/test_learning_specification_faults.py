"""Checks for evaluation leakage, CNL correspondence, and hold-release faults."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/paper1_cnl_learning'))
import learning_specification_faults as experiment


def example(profile, duration):
    if profile == 'pedestrian_entry':
        return dict(profile=profile, id='entry', specification=experiment.temporal.contract(duration / 1000),
                    clear_ms=3000, candidates=[dict(label='A', entry_ms=3000 + duration),
                                               dict(label='B', entry_ms=None)])
    return dict(profile=profile, id='hold', specification=experiment.hold.contract(duration),
                candidates=[dict(label='A', xy_mm=[[0, 0] for _ in experiment.hold.TIMES_MS])])


class LearningSpecificationFaultTests(unittest.TestCase):
    def test_valid_learning_specifications_and_round_trip(self):
        for profile, values in (('pedestrian_entry', (500, 1500)), ('position_hold', (500, 2000))):
            for duration in values:
                with self.subTest(profile=profile, duration=duration):
                    case = example(profile, duration)
                    result = experiment.evaluate(case, 'valid')
                    self.assertTrue(result['accepted'])
                    self.assertFalse(result['unknown'])
                    self.assertEqual(experiment.parse_sentence(profile, result['cnl']), case['specification'])

    def test_fault_detection_does_not_mutate_inputs(self):
        variants = ('duration_change', 'reverse_comparison', 'delete_release', 'unit_error',
                    'cnl_duration', 'cnl_negation')
        for profile in experiment.PROFILES:
            case = example(profile, 500)
            before = deepcopy(case)
            for kind in variants:
                with self.subTest(profile=profile, kind=kind):
                    result = experiment.evaluate(case, kind)
                    self.assertTrue(result['detected'])
                    self.assertFalse(result['accepted'])
                    self.assertFalse(result['unknown'])
                    self.assertEqual(case, before)

    def test_sentence_faults_are_not_detected_by_kernel_subset(self):
        for profile in experiment.PROFILES:
            for kind in ('cnl_duration', 'cnl_negation'):
                result = experiment.evaluate(example(profile, 500), kind)
                self.assertFalse(result['kernel_detected'])
                self.assertTrue(result['layers']['sentence'])

    def test_jointly_wrong_source_is_not_independent_evidence(self):
        for profile in experiment.PROFILES:
            result = experiment.evaluate(example(profile, 500), 'shared_source_error')
            self.assertNotEqual(result['original_specification'], result['trusted_source'])
            self.assertEqual(result['trusted_source'], result['candidate_specification'])
            self.assertTrue(result['accepted'])

    def test_hold_release_omission_rejects_post_hold_motion(self):
        result = experiment.evaluate(example('position_hold', 500), 'delete_release')
        probe = next(p for p in result['probes'] if p['id'] == 'sample-3-201-0')
        self.assertEqual(probe['expected'], 'SAT')
        self.assertEqual(probe['observed'], 'UNSAT')
        self.assertTrue(result['layers']['logic_rule'])
        self.assertEqual(result['consistency'], 'SAT')

    def test_hold_parser_requires_inclusive_endpoint_and_matching_times(self):
        text = experiment.hold.render(experiment.hold.contract(500))
        for changed in (text.replace('including the endpoint', 'excluding the endpoint'),
                        text.replace('t <= 0.5', 't <= 2.0'),
                        text.replace('0.200 m', '0.201 m')):
            with self.assertRaises(ValueError):
                experiment.parse_sentence('position_hold', changed)


if __name__ == '__main__':
    unittest.main()
