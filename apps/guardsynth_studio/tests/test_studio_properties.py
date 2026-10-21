"""Production 12-property checks, including controls that must remain unknown."""
from copy import deepcopy
import unittest
from guard_synth.studio_sequence import compile_sequence, verify_compiled
from .test_grounded_sequence import moment, definition, fact, guard


def checked(ms):
    return verify_compiled(compile_sequence(ms,{"sources":[]}))["scenes"][-1]


def prop(row, pid):
    return next(p for p in row["properties"]["results"] if p["property_id"]==pid)


class StudioPropertiesTest(unittest.TestCase):
    def test_all_twelve_reported_without_mutating_input(self):
        ms=[moment()];before=deepcopy(ms);row=checked(ms)
        self.assertEqual(ms,before)
        self.assertEqual([p['property_id'] for p in row['properties']['results']],[f'B{i}' for i in range(1,9)]+[f'A{i}' for i in range(1,5)])
        self.assertEqual(prop(row,'A1')['status'],'NOT_CHECKED')
        self.assertEqual(prop(row,'A4')['status'],'NOT_CHECKED')
        self.assertEqual(row['properties']['status'],'UNKNOWN')
        self.assertNotIn('property_input',row)

    def test_b1_unsupported_kind_is_reviewed(self):
        m=moment(facts=[fact(predicate='SIGNAL_GREEN',subject='e1',target=None)])
        self.assertEqual(prop(checked([m]),'B1')['status'],'UNKNOWN')

    def test_b2_old_evidence_cannot_release_current_condition(self):
        a=moment();b=moment(1,[],[fact('FALSE')],'ENTER','e2',previous=True)
        b['frame_ids']=['f','now'];b['current_evidence_refs']=['now'];b['coc']['observed_actions'][0]['evidence_refs']=['now']
        row=checked([a,b]);self.assertEqual(prop(row,'B2')['status'],'UNKNOWN')
        self.assertEqual(row['ledger']['path_blocked'],'ACTIVE')

    def test_b3_self_relation_and_corrected_direction(self):
        m=moment();m['coc']['relations']=[{'predicate':'AHEAD_OF','subject_ref':'e2','object_ref':'e2','truth':'TRUE','evidence_refs':['f']}]
        self.assertEqual(prop(checked([m]),'B3')['status'],'FAIL')
        m['coc']['relations'][0]['object_ref']='ego'
        self.assertEqual(prop(checked([m]),'B3')['status'],'PASS')

    def test_b4_same_id_cannot_change_definition(self):
        a=moment();b=moment(1,[definition(effect='ALLOW')],previous=True)
        self.assertEqual(prop(checked([a,b]),'B4')['status'],'FAIL')
        b['constraints']['new_definitions'][0]['condition_id']='another_condition'
        self.assertEqual(prop(checked([a,b]),'B4')['status'],'PASS')

    def test_b5_conflicting_lifecycle_and_unknown_release(self):
        d=definition(release_any_of=[guard()])
        self.assertEqual(prop(checked([moment(definitions=[d])]),'B5')['status'],'FAIL')
        row=checked([moment(),moment(1,[],[fact('UNKNOWN')],previous=True)])
        self.assertEqual(row['states']['path_blocked']['state'],'ACTIVE')
        self.assertEqual(prop(row,'B5')['status'],'PASS')

    def test_b6_forbidden_recorded_action_and_other_target(self):
        self.assertEqual(prop(checked([moment(action='ENTER',target='e2')]),'B6')['status'],'FAIL')
        self.assertEqual(prop(checked([moment(action='ENTER',target='e3')]),'B6')['status'],'PASS')

    def test_b6_missing_action_not_closed_world(self):
        d=definition(effect='REQUIRE',actions=['CONTINUE'],action_target_ref=None)
        m=moment(definitions=[d]);row=checked([m])
        self.assertNotIn('ACTION_CONTRADICTION',row['codes'])
        self.assertEqual(prop(row,'B6')['status'],'UNKNOWN')
        m['coc']['action_observation_complete']=True
        self.assertEqual(prop(checked([m]),'B6')['status'],'FAIL')

    def test_b7_applies_only_to_performed_matching_action(self):
        d=definition(effect='ALLOW',preconditions=[guard(predicate='PATH_CLEAR',subject='e2',target=None)])
        m=moment(definitions=[d],facts=[fact(),fact('FALSE',predicate='PATH_CLEAR',subject='e2',target=None)],action='ENTER',target='e2')
        self.assertEqual(prop(checked([m]),'B7')['status'],'FAIL')
        m['coc']['observed_actions'][0].update(code='HOLD',action_target_ref=None)
        self.assertEqual(prop(checked([m]),'B7')['status'],'NOT_APPLICABLE')

    def test_b8_completion_window_required_and_repair(self):
        d=definition(effect='ALLOW',expected_postconditions=[guard(predicate='IN',subject='ego',target='e2')])
        a=moment(definitions=[d],action='ENTER',target='e2');b=moment(1,[],[fact(),fact('FALSE',predicate='IN',subject='ego',target='e2')],previous=True)
        self.assertEqual(prop(checked([a,b]),'B8')['status'],'NOT_CHECKED')
        d['postcondition_window']='NEXT_OBSERVATION'
        self.assertEqual(prop(checked([a,b]),'B8')['status'],'FAIL')
        b['constraints']['facts'][-1]['truth']='TRUE'
        self.assertEqual(prop(checked([a,b]),'B8')['status'],'PASS')

    def test_b8_unperformed_forbidden_action_has_no_outcome_to_repair(self):
        d=definition(expected_postconditions=[guard('FALSE',predicate='IN',subject='ego',target='e2')])
        ms=[moment(definitions=[d],action='CONTINUE')];before=deepcopy(ms)
        row=checked(ms);p=prop(row,'B8')
        self.assertEqual(p['status'],'NOT_APPLICABLE')
        self.assertEqual(p['checks'][0]['reason'],'NO_RECORDED_ACTION')
        self.assertEqual(prop(row,'B6')['status'],'PASS')
        self.assertEqual(ms,before)

    def test_b8_next_scene_wait_is_not_a_source_less_repair(self):
        d=definition(effect='ALLOW',postcondition_window='NEXT_OBSERVATION',expected_postconditions=[guard(predicate='IN',subject='ego',target='e2')])
        p=prop(checked([moment(definitions=[d],action='ENTER',target='e2')]),'B8')
        self.assertEqual(p['status'],'NOT_CHECKED');self.assertTrue(p['informational'])
        self.assertEqual(p['checks'][0]['reason'],'NEXT_SCENE_PENDING')
        self.assertEqual(p['sources'][0]['path'],'/new_definitions/0')

    def test_b8_timing_gap_links_exact_origin_and_does_not_hide_behind_other_queries(self):
        d=definition(effect='ALLOW',expected_postconditions=[guard(predicate='IN',subject='ego',target='e2')])
        ready=deepcopy(d);ready.update(condition_id='ready',postcondition_window='NEXT_OBSERVATION')
        a=moment(definitions=[d,ready],action='ENTER',target='e2')
        b=moment(1,[],[fact(),fact(predicate='IN',subject='ego',target='e2')],previous=True)
        p=prop(checked([a,b]),'B8')
        self.assertEqual(p['status'],'UNKNOWN')
        gap=next(c for c in p['checks'] if c.get('code')=='POSTCONDITION_TIMING_REQUIRED')
        self.assertEqual(gap['sources'][0]['moment_id'],'m0')
        self.assertEqual(gap['sources'][0]['path'],'/new_definitions/0')
        self.assertTrue(any(c.get('query_id','').startswith('post_') for c in p['checks']))

    def test_b8_missing_future_fact_stays_unknown_with_editable_definition(self):
        d=definition(effect='ALLOW',postcondition_window='NEXT_OBSERVATION',expected_postconditions=[guard(predicate='IN',subject='ego',target='e2')])
        a=moment(definitions=[d],action='ENTER',target='e2');b=moment(1,[],previous=True)
        p=prop(checked([a,b]),'B8')
        self.assertEqual(p['status'],'UNKNOWN')
        gap=next(c for c in p['checks'] if c.get('code')=='POSTCONDITION_UNKNOWN')
        self.assertEqual(gap['sources'][0]['value']['expected_postconditions'],d['expected_postconditions'])

    def test_a1_explicit_claim_independent_evidence_and_repair(self):
        m=moment();m['coc']['reason_bindings']=[{'action_index':0,'explanation_excerpt':m['coc']['explanation'],'reasons':[guard('FALSE')]}]
        # Bind a condition to the actual HOLD tuple, independent of the reason.
        m['constraints']['new_definitions'][0].update(effect='ALLOW',actions=['HOLD'],action_target_ref=None)
        row=checked([m]);self.assertEqual(prop(row,'A1')['status'],'FAIL')
        self.assertIn('JUSTIFICATION_CONTRADICTION',row['codes'])
        m['coc']['reason_bindings'][0]['reasons'][0]['expected_truth']='TRUE'
        self.assertEqual(prop(checked([m]),'A1')['status'],'PASS')
        m['coc']['explanation']='사람이 새로 쓴 문장'
        self.assertEqual(prop(checked([m]),'A1')['status'],'UNKNOWN')

    def test_a1_inconsistent_evidence_does_not_prove_claim(self):
        m=moment(facts=[fact(),fact('FALSE')]);m['constraints']['new_definitions'][0].update(actions=['HOLD'],action_target_ref=None)
        m['coc']['reason_bindings']=[{'action_index':0,'explanation_excerpt':m['coc']['explanation'],'reasons':[guard()]}]
        self.assertEqual(prop(checked([m]),'A1')['status'],'UNKNOWN')

    def test_a1_direct_ego_reason_without_matching_constraint(self):
        m=moment(definitions=[],facts=[fact('FALSE',predicate='STOPPED',subject='ego',target=None)],action='CONTINUE')
        m['coc']['reason_bindings']=[{'action_index':0,'explanation_excerpt':m['coc']['explanation'],'reasons':[guard('FALSE',predicate='STOPPED',subject='ego',target=None)]}]
        self.assertEqual(prop(checked([m]),'A1')['status'],'PASS')

    def test_inconsistent_observations_do_not_pass_dependent_safety(self):
        row=checked([moment(facts=[fact(),fact('FALSE')])])
        self.assertEqual(prop(row,'B3')['status'],'FAIL')
        self.assertEqual(prop(row,'B6')['status'],'UNKNOWN')
        for pid in ('B7','B8'):self.assertEqual(prop(row,pid)['status'],'NOT_APPLICABLE')

    def test_previous_compiled_format_does_not_claim_new_properties(self):
        compiled=compile_sequence([moment()],{'sources':[]})
        compiled['version']='studio-grounded-sequential-coc-v0.2'
        for row in compiled['scenes']:row.pop('property_input')
        row=verify_compiled(compiled)['scenes'][0]
        self.assertTrue(all(p['status']=='NOT_CHECKED' for p in row['properties']['results']))

    def test_a2_scope_target_and_coverage_are_separate_from_truth(self):
        d=definition(effect='ALLOW');m=moment(definitions=[d],action='ENTER',target='e2')
        row=checked([m]);self.assertEqual(prop(row,'A2')['status'],'UNKNOWN')
        self.assertIn('REQUIRED_CONDITION_MISSING',row['codes'])
        d['preconditions']=[guard(predicate='PATH_CLEAR',subject='e3',target=None)]
        self.assertEqual(prop(checked([m]),'A2')['status'],'UNKNOWN')
        d['preconditions']=[guard(predicate='PATH_CLEAR',subject='e2',target=None)]
        self.assertEqual(prop(checked([m]),'A2')['status'],'PASS')
        self.assertEqual(prop(checked([m]),'B7')['status'],'UNKNOWN')

    def test_a3_or_permissions_and_retained_same_target_block(self):
        allow=definition(condition_id='allow',effect='ALLOW');block=definition()
        m=moment(definitions=[allow,block]);row=checked([m])
        self.assertEqual(prop(row,'A3')['checks'][0]['permission'],'BLOCKED')
        self.assertNotEqual(row['status'],'CONTRADICTION')
        block['action_target_ref']='e3'
        self.assertEqual(prop(checked([m]),'A3')['checks'][0]['permission'],'CONFIRMED')
        # One false alternative must not invalidate another ready ALLOW.
        other=deepcopy(allow);other.update(condition_id='alternative',activation_all_of=[guard('FALSE')])
        m['constraints']['new_definitions'].append(other)
        self.assertEqual(prop(checked([m]),'A3')['checks'][0]['permission'],'CONFIRMED')

    def test_a4_can_mismatch_repaired_and_stale_not_false(self):
        m=moment(action='CONTINUE');m['frame_ids'].append('CAN:0');m['current_evidence_refs']=['f','CAN:0'];m['coc']['observed_actions'][0]['evidence_refs'].append('CAN:0')
        m['vehicle_state']={'frames':[{'frame_timestamp_us':0,'age_us':0,'sample':{'timestamp_us':0,'vehicle_speed_kmh':8.3}}]}
        self.assertEqual(prop(checked([m]),'A4')['status'],'PASS')
        m['coc']['observed_actions'][0]['code']='HOLD';row=checked([m])
        self.assertEqual(prop(row,'A4')['status'],'FAIL');self.assertIn('CAN_ACTION_CONTRADICTION',row['codes'])
        m['vehicle_state']['frames'][0]['sample']['vehicle_speed_kmh']=1
        self.assertEqual(prop(checked([m]),'A4')['status'],'UNKNOWN')
        m['vehicle_state']['frames'][0]['age_us']=-1
        self.assertEqual(prop(checked([m]),'A4')['status'],'UNKNOWN')

    def test_property_module_signature_invalidates_results(self):
        from unittest.mock import patch
        from guard_synth.studio_sequence import tool_signature
        before=tool_signature()
        with patch('guard_synth.studio_properties.__file__',__file__):
            self.assertNotEqual(before,tool_signature())


if __name__=='__main__': unittest.main()
