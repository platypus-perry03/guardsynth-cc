"""Crossing passage ends a scoped candidate without inventing signal truth."""
import unittest

from guard_synth.studio_sequence import compile_sequence, verify_sequence
from guard_synth.studio_grounded_sequence import grounded_instructions
from .test_sequence import condition, scene, CATALOG
from .test_grounded_sequence import definition, guard, fact, moment


class ConstraintScopeTest(unittest.TestCase):
    def test_unknown_signal_can_end_with_reviewed_scope_exit(self):
        original = condition('UNKNOWN', condition_class='TRAFFIC_CONTROL', scope_state='UNKNOWN')
        ended = {**original, 'scope_state': 'ENDED', 'evidence_note': '이전·현재 영상에서 해당 횡단보도 통과 확인'}
        compiled = compile_sequence([scene(0, [ended]), scene(1)], CATALOG)
        self.assertEqual(compiled['scenes'][0]['ledger']['pedestrian_path'], 'RELEASED')
        self.assertEqual(compiled['pairs'][0]['carried_ids'], [])
        self.assertEqual(ended['truth'], 'UNKNOWN')
        self.assertEqual(original['scope_state'], 'UNKNOWN')

    def test_missing_scope_exit_evidence_does_not_clear_unknown_candidate(self):
        c = condition('UNKNOWN', scope_state='ENDED', evidence=False)
        compiled = compile_sequence([scene(0, [c]), scene(1)], CATALOG)
        self.assertEqual(compiled['scenes'][0]['ledger']['pedestrian_path'], 'UNKNOWN')
        self.assertIn('pedestrian_path', compiled['pairs'][0]['carried_ids'])

    def test_passage_fact_clears_only_its_zone_and_unknown_does_not_clear(self):
        g = guard(predicate='PASSAGE_COMPLETE', subject='ego', target='e2')
        d = definition(release_any_of=[g])
        for truth, target, expected in [('TRUE', 'e2', 'RELEASED'), ('UNKNOWN', 'e2', 'ACTIVE'), ('TRUE', 'e3', 'ACTIVE')]:
            f = fact(truth, predicate='PASSAGE_COMPLETE', subject='ego', target=target)
            out = verify_sequence([moment(definitions=[d]), moment(1, [], [f], previous=True)], {'sources': []})
            self.assertEqual(out['scenes'][1]['ledger']['path_blocked'], expected)

    def test_constraints_prompt_distinguishes_passage_from_invisibility(self):
        prompt = grounded_instructions('SEQ_CONSTRAINTS')
        self.assertIn('PASSAGE_COMPLETE(ego,zone)=TRUE', prompt)
        self.assertIn('보이지 않는 것만으로 해제하지 않는다', prompt)
        self.assertIn('진입 전에도 FALSE', prompt)

