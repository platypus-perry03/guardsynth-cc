"""Check oracle isolation, frozen scoring, and invalid-answer accounting."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/paper1_external_methods/run_reasoning_comparison.py'
spec = importlib.util.spec_from_file_location('reasoning_comparison', SOURCE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class ReasoningComparisonTests(unittest.TestCase):
    def test_answer_parser_does_not_read_letters_inside_words_or_resolve_ambiguity(self):
        for text in ('Because there is no rule.', 'B or C', 'E', 'SAT', ''):
            self.assertEqual(r.parse_answer(text, 'ABCD'), 'INVALID')
        self.assertEqual(r.parse_answer('The answer is (B).', 'ABCD'), 'B')
        self.assertEqual(r.parse_answer('C', 'AB'), 'INVALID')

    def test_model_payload_is_identical_under_changed_hidden_rules(self):
        for family in ('temporal', 'static', 'maneuver'):
            groups = {}
            for case in r.load_cases(family):
                text = r.first_text(case, 'plan_and_solve')
                if case['input_id'] in groups:
                    self.assertEqual(text, groups[case['input_id']])
                groups[case['input_id']] = text
                changed = dict(case, meta={'SECRET_RULE': 'FORBIDDEN_SENTINEL'}, target='FORBIDDEN_SENTINEL')
                self.assertEqual(text, r.first_text(changed, 'plan_and_solve'))
                self.assertNotIn('FORBIDDEN_SENTINEL', r.second_text(changed, 'zero_shot_cot', 'reason'))

    def test_all_archived_predictions_have_the_same_rule_scores(self):
        for family in ('temporal', 'static', 'maneuver'):
            cases = {(x['scene_id'], x['task'], x['contract_level']): x for x in r.load_cases(family)}
            for seed in r.SEEDS:
                for arm in ('p0', 'p1', 'p2'):
                    for row in r.read_rows(r.learning(family) / f'{arm}-seed{seed}/test.jsonl'):
                        case = cases[(row['scene_id'], row.get('subtype', 'temporal'), row['contract_level'])]
                        observed = r.score(case, row['prediction'])
                        self.assertEqual(observed['correct'], row['correct'])
                        self.assertEqual(observed['valid'], row['valid'])
                        if observed['valid']:
                            self.assertEqual(observed['violation'], row.get('violation', row.get('guard_violation')))

    def test_p1_inputs_distinguish_rules_without_leaking_oracle_metadata(self):
        for family in ('temporal', 'static', 'maneuver'):
            p0 = r.load_cases(family)
            p1 = r.load_cases(family, arm='p1')
            p2 = r.load_cases(family, arm='p2')
            self.assertEqual([x['id'] for x in p0], [x['id'] for x in p1])
            groups = {}
            for original, supplied, cnl in zip(p0, p1, p2):
                self.assertEqual(supplied['id'], cnl['id'])
                self.assertEqual(original['image_sha256'], supplied['image_sha256'])
                self.assertEqual(supplied['image_sha256'], cnl['image_sha256'])
                self.assertEqual(r.allowed_candidates(supplied), r.allowed_candidates(cnl))
                self.assertNotEqual(original['prompt'], supplied['prompt'])
                groups.setdefault(supplied['input_id'], set()).add(supplied['target'])
                changed = dict(supplied, meta={'SECRET': 'FORBIDDEN_SENTINEL'}, target='FORBIDDEN_SENTINEL')
                for method in r.TRIGGERS:
                    self.assertEqual(r.first_text(supplied, method), r.first_text(changed, method))
                    self.assertNotIn('FORBIDDEN_SENTINEL', r.second_text(changed, method, 'reason'))
            self.assertTrue(all(len(targets) == 1 for targets in groups.values()))

    def test_invalid_predictions_are_neither_removed_nor_called_safe(self):
        case = r.load_cases('temporal')[0]
        score = r.score(case, 'INVALID')
        self.assertIsNone(score['violation'])
        rows = [dict(task='temporal', scene_id=1, **score), dict(task='temporal', scene_id=1, valid=True, correct=True, violation=False)]
        result = r.summarize(rows)
        self.assertEqual(result['rows'], 2)
        self.assertEqual(result['accuracy'], .5)
        self.assertEqual(result['invalid_rate'], .5)
        self.assertEqual(result['pair_accuracy'], 0)

    def test_ps_uses_native_conditional_answer_markers(self):
        self.assertEqual(r.ps_answer_tail('Plan. Therefore, the answer is B.'), ' B.')
        self.assertIsNone(r.ps_answer_tail('B'))


if __name__ == '__main__':
    unittest.main()
