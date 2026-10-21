"""guardsynth-coc: positive/negative controls for the offline property probe."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

import z3

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import studio_property_probe as p


KINDS = {'ego': 'EGO', 'zone': 'ZONE', 'other': 'ZONE', 'signal': 'SIGNAL'}


def guard(predicate='PATH_CLEAR', subject='zone', target=None):
    return {'atom': {'predicate': predicate, 'subject_ref': subject, 'object_ref': target}, 'expected_truth': 'TRUE'}


def definition(effect='ALLOW', target='zone', cid='allow'):
    return {'condition_id': cid, 'effect': effect, 'subject_ref': 'ego', 'actions': ['ENTER'],
            'action_target_ref': target, 'movement_ref': None,
            'activation_all_of': [guard('SIGNAL_GREEN', 'signal'), guard('APPLIES_TO', 'signal', 'ego')],
            'preconditions': [guard(subject=target)]}


def request(speed=0, age=10000):
    return {'frames': [{'timestamp_us': 1000000}], 'vehicle_state': {'frames': [
        {'frame_timestamp_us': 1000000, 'age_us': age,
         'sample': {'timestamp_us': 1000000-age, 'vehicle_speed_kmh': speed}}]}}


def action(code='HOLD', sample_time=990000):
    return {'code': code, 'evidence_refs': ['CAN:' + str(sample_time)]}


class StudioPropertyProbeTest(unittest.TestCase):
    def test_p1_supported_contradicted_and_unknown_are_distinct(self):
        key = ('PATH_CLEAR', 'zone', None)
        for truth, expected in [('TRUE', 'SUPPORTED'), ('FALSE', 'CONTRADICTED'), ('UNKNOWN', 'UNCONFIRMED')]:
            result = p.justification_support(p.EvidenceModel([(key, truth)]), [guard()], KINDS)
            self.assertEqual(result['status'], expected)

    def test_p1_missing_binding_is_unavailable_not_a_proof(self):
        self.assertEqual(p.justification_support(p.EvidenceModel(), [], KINDS)['status'], 'CLAIM_BINDING_UNAVAILABLE')

    def test_p1_conflicting_premises_do_not_prove_every_claim(self):
        key = ('PATH_CLEAR', 'zone', None)
        model = p.EvidenceModel([(key, 'TRUE'), (key, 'FALSE')])
        self.assertEqual(p.justification_support(model, [guard()], KINDS)['status'], 'INPUT_CONFLICT')

    def test_p2_target_and_applicability_are_required_without_changes_to_input(self):
        d = definition();original = deepcopy(d)
        self.assertEqual(p.required_conditions(d, 'ENTER', KINDS)['status'], 'CHECKLIST_PRESENT')
        self.assertEqual(d, original)
        d['preconditions'] = [guard(subject='ego')]
        self.assertEqual(p.required_conditions(d, 'ENTER', KINDS)['missing'], [{'predicate': 'PATH_CLEAR', 'target': 'zone'}])
        d['activation_all_of'] = [guard('SIGNAL_GREEN', 'signal')]
        self.assertEqual({x['predicate'] for x in p.required_conditions(d, 'ENTER', KINDS)['missing']}, {'PATH_CLEAR', 'APPLIES_TO'})

    def test_p2_same_legacy_target_normalizes_but_unbound_and_other_targets_do_not(self):
        d = definition();d['preconditions'] = [guard(subject='ego', target='zone')]
        self.assertEqual(p.required_conditions(d, 'ENTER', KINDS)['status'], 'CHECKLIST_PRESENT')
        d['preconditions'] = [guard(subject='other')]
        self.assertEqual(p.required_conditions(d, 'ENTER', KINDS)['status'], 'CHECKLIST_OMISSION')

    def test_p3_same_target_blocked_and_released_permission(self):
        records = [(('SIGNAL_GREEN', 'signal', None), 'TRUE'), (('APPLIES_TO', 'signal', 'ego'), 'TRUE'), (('PATH_CLEAR', 'zone', None), 'TRUE')]
        d = definition();block = definition('FORBID', cid='block')
        for state, active, expected in [('ACTIVE', True, 'PERMISSION_BLOCKED'), ('RELEASED', False, 'SUPPORTED'), ('UNKNOWN', False, 'UNCONFIRMED')]:
            result = p.permission_support(p.EvidenceModel(records), d, 'ENTER', [d, block], {'block': {'state': state, 'active_obligation': active}}, KINDS)
            self.assertEqual(result['status'], expected)
            self.assertEqual(result['overlap']['status'], 'UNSAT' if state == 'RELEASED' else 'SAT')

    def test_p3_different_target_movement_and_action_do_not_block(self):
        records = [(('SIGNAL_GREEN', 'signal', None), 'TRUE'), (('APPLIES_TO', 'signal', 'ego'), 'TRUE'), (('PATH_CLEAR', 'zone', None), 'TRUE')]
        for field, value in [('action_target_ref', 'other'), ('movement_ref', 'different_movement'), ('actions', ['STOP'])]:
            d = definition();block = definition('FORBID', cid='block');block[field] = value
            result = p.permission_support(p.EvidenceModel(records), d, 'ENTER', [d, block], {'block': {'state': 'ACTIVE', 'active_obligation': True}}, KINDS)
            self.assertEqual(result['status'], 'SUPPORTED')
            self.assertEqual(result['blocker_condition_ids'], [])

    def test_p3_candidate_condition_false_is_not_a_CoC_contradiction(self):
        d = definition();model = p.EvidenceModel([(('SIGNAL_GREEN', 'signal', None), 'FALSE')])
        result = p.permission_support(model, d, 'ENTER', [d], {}, KINDS)
        self.assertEqual(result['status'], 'CONDITION_NOT_MET')

    def test_p3_unsupported_guard_does_not_establish_permission(self):
        d = definition();d['preconditions'] = [guard(subject='ego')]
        records = [(('SIGNAL_GREEN', 'signal', None), 'TRUE'), (('APPLIES_TO', 'signal', 'ego'), 'TRUE')]
        result = p.permission_support(p.EvidenceModel(records), d, 'ENTER', [d], {}, KINDS)
        self.assertEqual(result['status'], 'UNCONFIRMED')
        self.assertTrue(result['invalid_guard_indexes'])

    def test_uncertain_same_id_cannot_support_current_justification(self):
        previous = [{'entity_id': k, 'kind': v, 'description': k} for k, v in KINDS.items()]
        entities = [{**e, 'identity_status': 'UNCERTAIN', 'previous_entity_ref': None} for e in previous]
        coc = {'entities': entities, 'relations': [{'predicate': 'PATH_CLEAR', 'subject_ref': 'zone', 'object_ref': None, 'truth': 'TRUE', 'evidence_refs': ['now']}]}
        model, kinds = p.evidence_model(coc, {'facts': []}, previous, ['now'])
        self.assertEqual(p.justification_support(model, [guard()], kinds)['status'], 'UNCONFIRMED')

    def test_p4_consistent_and_contradictory_motion(self):
        for code, speed, expected in [('HOLD', 0, 'CAN_RECORD_CONSISTENT'), ('HOLD', 15, 'CAN_RECORD_CONTRADICTION'), ('CONTINUE', 15, 'CAN_RECORD_CONSISTENT'), ('CONTINUE', 0, 'CAN_RECORD_CONTRADICTION')]:
            self.assertEqual(p.can_action_support(action(code), request(speed))['status'], expected)

    def test_p4_stale_future_gray_and_unlinked_are_not_contradictions(self):
        self.assertEqual(p.can_action_support(action(sample_time=300000), request(15, 700000))['status'], 'CAN_ALIGNMENT_UNCONFIRMED')
        self.assertEqual(p.can_action_support(action(sample_time=1010000), request(15, -10000))['status'], 'CAN_ALIGNMENT_UNCONFIRMED')
        self.assertEqual(p.can_action_support(action(), request(1))['status'], 'MOTION_GRAY_ZONE')
        self.assertEqual(p.can_action_support(action(sample_time=980000), request(15))['status'], 'CAN_LINK_UNAVAILABLE')

    def test_p4_enter_start_and_stop_require_other_evidence(self):
        self.assertEqual(p.can_action_support(action('ENTER'), request())['status'], 'NOT_APPLICABLE')
        for code in ('START', 'STOP'):
            self.assertEqual(p.can_action_support(action(code), request())['status'], 'TRANSITION_BINDING_UNAVAILABLE')

    def test_old_frame_and_CAN_cannot_prove_current_signal(self):
        coc = {'entities': [{'entity_id': k, 'kind': v, 'description': k, 'identity_status': 'NEW_LOCAL', 'previous_entity_ref': None} for k, v in KINDS.items()],
               'relations': [{'predicate': 'SIGNAL_GREEN', 'subject_ref': 'signal', 'object_ref': None, 'truth': 'TRUE', 'evidence_refs': ['old', 'CAN:1']}]}
        model, kinds = p.evidence_model(coc, {'facts': []}, [], ['now', 'CAN:1'])
        self.assertEqual(p.justification_support(model, [guard('SIGNAL_GREEN', 'signal')], kinds)['status'], 'UNCONFIRMED')

    def test_can_alone_cannot_prove_path_clear(self):
        coc = {'entities': [{'entity_id': k, 'kind': v, 'description': k, 'identity_status': 'NEW_LOCAL', 'previous_entity_ref': None} for k, v in KINDS.items()], 'relations': []}
        con = {'facts': [{'atom': guard()['atom'], 'truth': 'TRUE', 'evidence_refs': ['CAN:1'], 'evidence_note': 'CAN shows moving'}]}
        model, kinds = p.evidence_model(coc, con, [], ['now', 'CAN:1'])
        self.assertEqual(p.justification_support(model, [guard()], kinds)['status'], 'UNCONFIRMED')


if __name__ == '__main__':
    unittest.main()
