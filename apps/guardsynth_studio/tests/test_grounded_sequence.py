"""Grounded recorded-action profile: concrete targets, guards and edit pointers."""
from copy import deepcopy
import unittest
from guard_synth import studio_sequence as sequence

CATALOG = {"sources": []}

def atom(predicate="PATH_CONFLICT", subject="e1", target="e2"):
    return {"predicate": predicate, "subject_ref": subject, "object_ref": target}

def guard(truth="TRUE", **kwargs):
    return {"atom": atom(**kwargs), "expected_truth": truth}

def definition(**changes):
    value = {"condition_id":"path_blocked", "condition_class":"VULNERABLE_ROAD_USER", "subject_ref":"ego", "condition_target_refs":["e1"], "action_target_ref":"e2", "movement_ref":None, "description":"보행자가 진입 경로를 점유함", "effect":"FORBID", "actions":["ENTER"], "activation_all_of":[guard()], "release_any_of":[guard("FALSE")], "preconditions":[], "expected_postconditions":[], "source_refs":[]}
    value.update(changes)
    return value

def fact(truth="TRUE", **kwargs):
    return {"atom":atom(**kwargs), "truth":truth, "evidence_refs":["f"], "evidence_note":"영상 확인"}

def moment(index=0, definitions=None, facts=None, action="HOLD", target=None, previous=False):
    entities=[{"entity_id":eid,"kind":kind,"description":"장면 대상", "identity_status":"MATCHED_PREVIOUS" if previous else "NEW_LOCAL", "previous_entity_ref":eid if previous else None,"evidence_refs":["f"]} for eid,kind in [("ego","EGO"),("e1","PEDESTRIAN"),("e2","ZONE"),("e3","ZONE")]]
    return {"id":"m"+str(index),"ordinal":index,"t0_us":index*1000000,"frame_ids":["f"],"reviewed":True,"coc":{"entities":entities,"relations":[],"observed_actions":[{"code":action,"subject_ref":"ego","action_target_ref":target,"movement_ref":None,"evidence_refs":["f"]}],"observations":"실제 장면","explanation":"기록 행동 설명","unknowns":[],"evidence_refs":["f"]},"constraints":{"new_definitions":[definition()] if definitions is None else definitions,"facts":[fact()] if facts is None else facts,"unresolved_previous_condition_refs":[],"unknowns":[]}}

class GroundedSequenceTest(unittest.TestCase):
    def run_sequence(self, moments):
        return sequence.verify_sequence(moments,CATALOG)

    def test_inherited_target_metadata_survives_unwritten_and_offscreen_scenes(self):
        from guard_synth.studio_grounded_sequence import compile_grounded_sequence,verify_grounded_compiled
        ms=[moment(),moment(1,[],[],previous=True),moment(2,[],[]),moment(3,[],[])]
        ms[1]['coc']={};ms[1]['constraints']={}
        for m in ms[2:]:m['coc']['entities']=m['coc']['entities'][:1]
        before=deepcopy(ms);full=self.run_sequence(ms)
        first=compile_grounded_sequence(ms[:2],CATALOG)
        streamed=verify_grounded_compiled(compile_grounded_sequence(ms[2:],CATALOG,first['continuation_summary']))
        for row in full['scenes'][2:]+streamed['scenes']:
            self.assertFalse({'UNBOUND_TARGET','UNSUPPORTED_ACTION_TARGET','UNSUPPORTED_ATOM'} & set(row['codes']))
            self.assertEqual(row['ledger']['path_blocked'],'ACTIVE')
            self.assertIn('EVIDENCE_MISSING',row['codes'])
        self.assertEqual(streamed['pending'],full['pending'])
        metadata=streamed['continuation_summary']['ledger']['path_blocked']['target_entities']
        self.assertEqual(set(metadata),{'ego','e1','e2'})
        self.assertTrue(all(set(e)=={'entity_id','kind','description'} for e in metadata.values()))
        self.assertEqual(ms,before)

    def test_retained_metadata_allows_current_evidence_to_release_offscreen_target(self):
        from guard_synth.studio_grounded_sequence import grounded_state_summary,definition_entities
        d=definition(release_any_of=[guard(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')])
        ms=[moment(definitions=[d]),moment(1,[],[]),moment(2,[],[fact(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')])]
        for m in ms[1:]:m['coc']['entities']=m['coc']['entities'][:1]
        row=self.run_sequence(ms)['scenes'][-1]
        self.assertEqual(row['ledger']['path_blocked'],'RELEASED')
        self.assertNotIn('UNSUPPORTED_ATOM',row['codes'])
        summary=grounded_state_summary([d],{'path_blocked':'ACTIVE'},ms[-1]['constraints'],{'f'},ms[-1]['coc'],[],list(definition_entities(d,ms[0]['coc']['entities']).values()))
        self.assertEqual(summary,{'path_blocked':'RELEASED'})
        ms[-1]['constraints']['facts'][0]['evidence_refs']=[]
        self.assertEqual(self.run_sequence(ms)['scenes'][-1]['ledger']['path_blocked'],'ACTIVE')

    def test_reused_local_id_after_gap_cannot_release_inherited_constraint(self):
        ms=[moment(),moment(1,[],[]),moment(2,[],[fact('FALSE')])]
        ms[1]['coc']['entities']=ms[1]['coc']['entities'][:1]
        row=self.run_sequence(ms)['scenes'][-1]
        self.assertIn('ENTITY_IDENTITY_UNCERTAIN',row['codes'])
        self.assertEqual(row['ledger']['path_blocked'],'ACTIVE')

    def test_genuinely_unknown_definition_target_still_requires_repair(self):
        # Saved malformed definitions are diagnosed without inventing metadata.
        from guard_synth.studio_grounded_sequence import compile_grounded_sequence
        initial=compile_grounded_sequence([moment()],CATALOG)['continuation_summary']
        initial['ledger']['path_blocked']['definition']['condition_target_refs']=['missing']
        row=compile_grounded_sequence([moment(1,[],[],previous=True)],CATALOG,initial)['scenes'][0]
        self.assertIn('UNBOUND_TARGET',row['codes'])

    def test_inherited_lifecycle_conflict_links_current_observations(self):
        d=definition(activation_all_of=[guard(predicate='ZONE_CLOSED',subject='e2',target=None)],
                     release_any_of=[guard(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')])
        closed=fact(predicate='ZONE_CLOSED',subject='e2',target=None)
        passed=fact(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')
        ms=[moment(10,[d],[closed,{**passed,'truth':'FALSE'}]),moment(11,[],[closed,passed],previous=True)]
        before=deepcopy(ms);row=self.run_sequence(ms)['scenes'][1]
        issue=next(i for i in row['review_items'] if i['code']=='LIFECYCLE_CONFLICT')
        self.assertEqual({(s['moment_id'],s['path']) for s in issue['sources']},
                         {('m10','/new_definitions/0'),('m11','/facts/0'),('m11','/facts/1')})
        self.assertEqual(row['states']['path_blocked']['state'],'CONFLICT')
        self.assertEqual(ms,before)
        ms[1]['constraints']['facts'][1]['truth']='FALSE'
        self.assertEqual(self.run_sequence(ms)['scenes'][1]['states']['path_blocked']['state'],'ACTIVE')
        ms[1]['constraints']['facts'][1]['truth']='UNKNOWN'
        unknown=self.run_sequence(ms)['scenes'][1]
        self.assertEqual(unknown['states']['path_blocked']['state'],'ACTIVE')
        self.assertIn('EVIDENCE_MISSING',unknown['codes'])
        ms[1]['constraints']['facts'][1]['truth']='TRUE'
        ms[0]['constraints']['new_definitions'][0]['activation_all_of'].append(
            guard('FALSE',predicate='PASSAGE_COMPLETE',subject='ego',target='e2'))
        released=self.run_sequence(ms)['scenes'][1]
        self.assertEqual(released['states']['path_blocked']['state'],'RELEASED')
        self.assertNotIn('LIFECYCLE_CONFLICT',released['codes'])

    def test_lifecycle_conflicting_claims_link_both_current_components(self):
        m=moment(11,facts=[fact(),fact('FALSE')]);a=deepcopy(m['constraints']['facts'][0]['atom'])
        m['coc']['relations']=[{**a,'truth':'TRUE','evidence_refs':['f']}]
        row=self.run_sequence([m])['scenes'][0]
        issue=next(i for i in row['review_items'] if i['code']=='LIFECYCLE_CONFLICT')
        self.assertTrue(any(s['component']=='sequence_coc' and s['path']=='/relations/0' for s in issue['sources']))
        self.assertTrue(any(s['path']=='/facts/1' for s in issue['sources']))

    def test_v2_schema_binds_actual_entities_and_evidence(self):
        from guard_synth.studio_grounded_sequence import grounded_schema,validate_grounded
        m=moment();context={"coc":m["coc"],"previous_entities":[],"evidence_refs":["f"]}
        schema=grounded_schema("SEQ_CONSTRAINTS",context)
        self.assertEqual(schema["properties"]["facts"]["items"]["properties"]["atom"]["properties"]["subject_ref"]["enum"],["e1","e2","e3","ego"])
        for field in ("subject_ref","object_ref"):
            bad=deepcopy(m["constraints"]);bad["facts"][0]["atom"][field]="invented"
            with self.assertRaises(ValueError):validate_grounded("SEQ_CONSTRAINTS",bad,{"f"},set(),context)
        bad=deepcopy(m["coc"]);bad["relations"]=[{"**":None}]
        with self.assertRaises(ValueError):validate_grounded("SEQ_COC",bad,{"f"},set())

    def test_unknown_release_retains_active_and_names_original_sources(self):
        ms=[moment(),moment(1,[],[fact("UNKNOWN")],"ENTER","e2", previous=True)]
        before=deepcopy(ms);out=self.run_sequence(ms)
        self.assertEqual(ms,before)
        self.assertEqual(out["pending"],[{"condition_id":"path_blocked","state":"ACTIVE"}])
        row=out["scenes"][1];self.assertIn("ACTION_CONTRADICTION",row["codes"])
        finding=next(r for r in row["review_items"] if r["code"]=="ACTION_CONTRADICTION")
        self.assertTrue(any(s["path"]=="/observed_actions/0" and s["moment_id"]=="m1" for s in finding["sources"]))
        self.assertTrue(any(s["path"]=="/new_definitions/0" and s["moment_id"]=="m0" for s in finding["sources"]))
        self.assertEqual(row["verification"]["smt"]["engine"],"Z3_BOUNDED_SMT")

    def test_confirmed_release_and_other_target_are_not_action_contradictions(self):
        out=self.run_sequence([moment(),moment(1,[],[fact("FALSE")],"ENTER","e2", previous=True)])
        self.assertNotIn("ACTION_CONTRADICTION",out["scenes"][1]["codes"])
        self.assertEqual(out["pending"],[])
        other=self.run_sequence([moment(action="ENTER",target="e3")])
        self.assertNotIn("ACTION_CONTRADICTION",other["scenes"][0]["codes"])

    def test_missing_evidence_cannot_clear_active(self):
        f=fact("FALSE");f["evidence_refs"]=[]
        out=self.run_sequence([moment(),moment(1,[],[f],"ENTER","e2", previous=True)])
        self.assertEqual(out["scenes"][1]["ledger"]["path_blocked"],"ACTIVE")
        self.assertIn("EVIDENCE_MISSING",out["scenes"][1]["codes"])

    def test_directional_relations_are_smt_constraints_with_edit_pointer(self):
        m=moment();m["coc"]["relations"]=[{"subject_ref":"e1","predicate":"LEFT_OF","object_ref":"ego","truth":"TRUE","evidence_refs":["f"]},{"subject_ref":"ego","predicate":"LEFT_OF","object_ref":"e1","truth":"TRUE","evidence_refs":["f"]}]
        out=self.run_sequence([m]);row=out["scenes"][0]
        self.assertIn("RELATION_CONTRADICTION",row["codes"])
        self.assertEqual(row["verification"]["smt"]["results"][0]["status"],"UNSAT")
        self.assertTrue(any(s["path"]=="/relations/1" for r in row["review_items"] for s in r["sources"]))

    def test_same_atom_conflicts_are_not_resolved_by_order(self):
        out=self.run_sequence([moment(facts=[fact(),fact("FALSE")])])
        self.assertIn("OBSERVATION_CONFLICT",out["scenes"][0]["codes"])

    def test_immutable_definition_drift_is_visible_without_repair(self):
        out=self.run_sequence([moment(),moment(1,[definition(description="달라진 조건")],[fact("UNKNOWN")], previous=True)])
        self.assertIn("IDENTITY_CONFLICT",out["scenes"][1]["codes"])
        self.assertEqual(out["scenes"][1]["constraints"][0]["description"],"보행자가 진입 경로를 점유함")

    def test_partial_start_empty_unknown_and_unsupported_are_reviewed(self):
        for m in [moment(definitions=[],facts=[]),moment(facts=[fact("UNKNOWN")]),moment(definitions=[definition(condition_class=None)]),moment(definitions=[definition(activation_all_of=[])])]:
            with self.subTest(m=m):self.assertEqual(self.run_sequence([m])["status"],"REVIEW_REQUIRED")
        m=moment(12);m["constraints"]["unresolved_previous_condition_refs"]=["earlier_missing"]
        self.assertIn("PRIOR_CONTEXT_MISSING",self.run_sequence([m])["scenes"][0]["codes"])

    def test_missing_legal_sources_are_separate_from_logical_status(self):
        out=self.run_sequence([moment()]);self.assertEqual(out["status"],"PASS")
        self.assertEqual(out["source_status"],"REVIEW_REQUIRED")
        self.assertFalse(out["training_eligible"])

    def test_preconditions_cannot_create_confirmed_permission(self):
        d=definition(effect="ALLOW",preconditions=[guard(predicate="PATH_CLEAR",subject="e2",target=None)])
        out=self.run_sequence([moment(definitions=[d],action="ENTER",target="e2")])
        self.assertIn("PRECONDITION_UNKNOWN",out["scenes"][0]["codes"])
        self.assertEqual(out["status"],"REVIEW_REQUIRED")

    def test_future_postconditions_are_not_asserted_as_current_facts(self):
        d=definition(effect="ALLOW",expected_postconditions=[guard(predicate="IN",subject="ego",target="e2")],postcondition_window="NEXT_OBSERVATION")
        out=self.run_sequence([moment(definitions=[d],action="ENTER",target="e2")])
        self.assertNotIn("POSTCONDITION_CONTRADICTION",out["scenes"][0]["codes"])
        next_m=moment(1,[],[fact(),fact("FALSE",predicate="IN",subject="ego",target="e2")], previous=True)
        pair=self.run_sequence([moment(definitions=[d],action="ENTER",target="e2"),next_m])
        self.assertIn("POSTCONDITION_CONTRADICTION",pair["scenes"][1]["codes"])

    def test_mixed_legacy_and_missing_data_become_reviewable_gaps(self):
        from .test_sequence import scene
        out=self.run_sequence([scene(0),moment(1, previous=True)])
        self.assertIn("LEGACY_INPUT_GAP",out["scenes"][0]["codes"])
        missing=moment();missing["coc"]=None;missing["constraints"]=None
        self.assertEqual(self.run_sequence([missing])["status"],"REVIEW_REQUIRED")

    def test_verified_render_includes_lifecycle_and_preserves_original(self):
        m=moment();compiled=sequence.compile_sequence([m],CATALOG);verified=sequence.verify_compiled(compiled)
        out=sequence.render_verified(compiled,verified)
        self.assertIn("해제",out["samples"][0]["text"])
        self.assertEqual(out["samples"][0]["status"],"PASS")

    def test_previous_only_evidence_cannot_confirm_current_release(self):
        a=moment();b=moment(1,[],[fact("FALSE")],"ENTER","e2", previous=True)
        b["frame_ids"]=["f","now"];b["current_evidence_refs"]=["now"]
        b["coc"]["evidence_refs"]=["now"];b["coc"]["observed_actions"][0]["evidence_refs"]=["now"]
        out=self.run_sequence([a,b])
        self.assertEqual(out["scenes"][1]["ledger"]["path_blocked"],"ACTIVE")
        self.assertIn("ACTION_CONTRADICTION",out["scenes"][1]["codes"])

    def test_incremental_summary_retains_active_with_unknown_release(self):
        from guard_synth.studio_grounded_sequence import grounded_state_summary
        prior={"path_blocked":"ACTIVE"}
        self.assertEqual(grounded_state_summary([definition()],prior,moment(facts=[fact("UNKNOWN")])["constraints"]),prior)
        self.assertEqual(grounded_state_summary([definition()],prior,moment(facts=[fact("FALSE")])["constraints"]),{"path_blocked":"RELEASED"})

    def test_hyphen_condition_ids_are_valid_and_free_text_limits_do_not_block_logic(self):
        m=moment(definitions=[definition(condition_id="cand-001")]);m["coc"]["unknowns"]=["거리 수치는 확인 안 됨"]
        out=self.run_sequence([m]);self.assertEqual(out["status"],"PASS")
        self.assertTrue(out["scenes"][0]["notes"])

    def test_unary_and_entity_kind_mismatch_cannot_be_pass(self):
        for bad in [fact(predicate="SIGNAL_RED",subject="e1",target="e2"),fact(predicate="PATH_CONFLICT",subject="e1",target=None)]:
            m=moment(facts=[fact(),bad]);out=self.run_sequence([m])
            self.assertIn("UNSUPPORTED_ATOM",out["scenes"][0]["codes"])
            self.assertEqual(out["status"],"REVIEW_REQUIRED")

    def test_spatial_cycle_is_unsat_and_maps_only_involved_relations(self):
        m=moment();m["coc"]["relations"]=[{"subject_ref":a,"predicate":"LEFT_OF","object_ref":b,"truth":"TRUE","evidence_refs":["f"]} for a,b in [("e1","e2"),("e2","e3"),("e3","e1")]]
        m["coc"]["relations"].append({"subject_ref":"ego","predicate":"STOPPED","object_ref":None,"truth":"TRUE","evidence_refs":["f"]})
        out=self.run_sequence([m]);row=out["scenes"][0]
        self.assertIn("RELATION_CONTRADICTION",row["codes"])
        issue=next(r for r in row["review_items"] if r["code"]=="RELATION_CONTRADICTION")
        paths={s["path"] for s in issue["sources"]}
        self.assertEqual(paths,{"/relations/0","/relations/1","/relations/2"})

    def test_release_alone_does_not_assert_action_completion(self):
        d=definition(expected_postconditions=[guard("FALSE",predicate="IN",subject="ego",target="e2")])
        a=moment(definitions=[d]);b=moment(1,[],[fact("FALSE"),fact("TRUE",predicate="IN",subject="ego",target="e2")], previous=True)
        out=self.run_sequence([a,b]);self.assertNotIn("POSTCONDITION_CONTRADICTION",out["scenes"][1]["codes"])

    def test_uncertain_or_replaced_entity_cannot_confirm_release(self):
        for identity,kind,description in [("UNCERTAIN","PEDESTRIAN","장면 대상"),("NEW_LOCAL","VEHICLE","다른 대상")]:
            a=moment();b=moment(1,[],[fact("FALSE")],"ENTER","e2", previous=True)
            b["coc"]["entities"][1].update(identity_status=identity,kind=kind,description=description)
            out=self.run_sequence([a,b]);row=out["scenes"][1]
            self.assertEqual(row["ledger"]["path_blocked"],"ACTIVE")
            self.assertIn("ENTITY_IDENTITY_UNCERTAIN",row["codes"])

    def test_matched_previous_identity_requires_same_kind_and_reference(self):
        a=moment();b=moment(1,[],[fact("FALSE")], previous=True);b["coc"]["entities"][1].update(identity_status="MATCHED_PREVIOUS",previous_entity_ref=None)
        out=self.run_sequence([a,b]);self.assertIn("ENTITY_IDENTITY_UNCERTAIN",out["scenes"][1]["codes"])

    def test_current_action_outside_candidate_target_requires_coverage_review(self):
        out=self.run_sequence([moment(action="ENTER",target="e3")])
        self.assertIn("ACTION_COVERAGE_MISSING",out["scenes"][0]["codes"])
        self.assertEqual(out["status"],"REVIEW_REQUIRED")

    def test_actor_to_ego_path_conflict_and_scoped_properties_are_supported(self):
        d=definition(activation_all_of=[guard(target="ego")],release_any_of=[guard("FALSE",target="ego")])
        m=moment(definitions=[d],facts=[fact(target="ego"),fact(predicate="PASSAGE_COMPLETE",subject="ego",target="e2")])
        out=self.run_sequence([m]);self.assertEqual(out["status"],"PASS")

    def test_summary_and_compiler_use_coc_claims_and_uncertain_identity_together(self):
        from guard_synth.studio_grounded_sequence import grounded_state_summary
        m=moment(facts=[fact("UNKNOWN")]);m["coc"]["relations"]=[{"subject_ref":"e1","predicate":"PATH_CONFLICT","object_ref":"e2","truth":"TRUE","evidence_refs":["f"]}]
        states=grounded_state_summary([definition()],{},m["constraints"],{"f"},current_coc=m["coc"])
        self.assertEqual(states,{"path_blocked":"ACTIVE"})
        m["coc"]["entities"][1]["identity_status"]="UNCERTAIN"
        states=grounded_state_summary([definition()],{},m["constraints"],{"f"},current_coc=m["coc"])
        self.assertEqual(states,{"path_blocked":"UNKNOWN"})

    def test_partial_start_with_false_activation_and_no_release_keeps_unknown_prior(self):
        d=definition(release_any_of=[guard(predicate="PASSAGE_COMPLETE",subject="ego",target="e2")])
        m=moment(definitions=[d],facts=[fact("FALSE"),fact("FALSE",predicate="PASSAGE_COMPLETE",subject="ego",target="e2")])
        out=self.run_sequence([m]);self.assertEqual(out["scenes"][0]["ledger"]["path_blocked"],"UNKNOWN")
        self.assertEqual(out["status"],"REVIEW_REQUIRED")

    def test_reused_solver_formulas_rebind_source_pointers_to_current_moment(self):
        ms=[]
        for index in (0,1):
            m=moment(index,[] if index else None,previous=bool(index))
            m["coc"]["relations"]=[{"subject_ref":a,"predicate":"LEFT_OF","object_ref":b,"truth":"TRUE","evidence_refs":["f"]} for a,b in [("e1","ego"),("ego","e1")]]
            ms.append(m)
        out=self.run_sequence(ms)
        for index,row in enumerate(out["scenes"]):
            issue=next(i for i in row["review_items"] if i["code"]=="RELATION_CONTRADICTION")
            self.assertEqual({s["moment_id"] for s in issue["sources"]},{"m"+str(index)})

    def test_same_kind_new_local_id_cannot_clear_previous_subject(self):
        a=moment();b=moment(1,[],[fact("FALSE")],"ENTER","e2", previous=True)
        b["coc"]["entities"][1].update(identity_status="NEW_LOCAL",previous_entity_ref=None)
        out=self.run_sequence([a,b]);self.assertEqual(out["scenes"][1]["ledger"]["path_blocked"],"ACTIVE")
        self.assertIn("ENTITY_IDENTITY_UNCERTAIN",out["scenes"][1]["codes"])

    def test_conflicting_scene_cannot_erase_prior_active_obligation(self):
        ms=[moment(),moment(1,[],[fact("CONFLICT")], previous=True),moment(2,[],[fact("UNKNOWN")],"ENTER","e2", previous=True)]
        out=self.run_sequence(ms)
        self.assertEqual(out["scenes"][2]["ledger"]["path_blocked"],"ACTIVE")
        self.assertIn("ACTION_CONTRADICTION",out["scenes"][2]["codes"])
        from guard_synth.studio_grounded_sequence import grounded_state_summary
        middle=grounded_state_summary([definition()],{"path_blocked":"ACTIVE"},ms[1]["constraints"])
        after=grounded_state_summary([definition()],middle,ms[2]["constraints"])
        self.assertEqual(after,{"path_blocked":"ACTIVE"})

    def test_conflicting_fact_sources_keep_original_truth_and_note(self):
        out=self.run_sequence([moment(facts=[fact("TRUE"),fact("FALSE")])])
        issue=next(i for i in out["scenes"][0]["review_items"] if i["code"]=="OBSERVATION_CONFLICT")
        self.assertEqual({s["value"]["truth"] for s in issue["sources"]},{"TRUE","FALSE"})
        self.assertTrue(all(s["value"]["evidence_note"]=="영상 확인" for s in issue["sources"]))

    def test_bounded_continuation_matches_full_sequence_and_retains_source_origin(self):
        from guard_synth.studio_grounded_sequence import compile_grounded_sequence,verify_grounded_compiled
        ms=[moment(),moment(1,[],[fact("CONFLICT")], previous=True),moment(2,[],[fact("UNKNOWN")],"ENTER","e2", previous=True)]
        first=compile_grounded_sequence(ms[:2],CATALOG)
        streamed=verify_grounded_compiled(compile_grounded_sequence(ms[2:],CATALOG,initial_summary=first["continuation_summary"]))
        full=self.run_sequence(ms)
        self.assertEqual(streamed["scenes"][0]["codes"],full["scenes"][2]["codes"])
        self.assertEqual(streamed["pending"],full["pending"])
        self.assertEqual(streamed["scenes"][0]["status"],"CONTRADICTION")
        issue=next(i for i in streamed["scenes"][0]["review_items"] if i["code"]=="ACTION_CONTRADICTION")
        self.assertTrue(any(s["moment_id"]=="m0" for s in issue["sources"]))
        self.assertNotIn("moments",streamed["continuation_summary"])
        self.assertEqual(len(streamed["continuation_summary"]["ledger"]),1)

    def test_bounded_continuation_checks_only_performed_prior_postcondition(self):
        from guard_synth.studio_grounded_sequence import compile_grounded_sequence,verify_grounded_compiled
        d=definition(effect="ALLOW",expected_postconditions=[guard(predicate="IN",subject="ego",target="e2")],postcondition_window="NEXT_OBSERVATION")
        a=moment(definitions=[d],action="ENTER",target="e2");b=moment(1,[],[fact(),fact("FALSE",predicate="IN",subject="ego",target="e2")], previous=True)
        first=compile_grounded_sequence([a],CATALOG)
        checked=verify_grounded_compiled(compile_grounded_sequence([b],CATALOG,initial_summary=first["continuation_summary"]))
        self.assertIn("POSTCONDITION_CONTRADICTION",checked["scenes"][0]["codes"])

    def test_enter_target_actor_is_unsupported_in_observation_and_allow_candidate(self):
        m=moment(definitions=[definition(effect="ALLOW",action_target_ref="e1")],action="ENTER",target="e1")
        out=self.run_sequence([m]);row=out["scenes"][0]
        self.assertIn("UNSUPPORTED_ACTION_TARGET",row["codes"])
        self.assertEqual(out["status"],"REVIEW_REQUIRED")
        self.assertFalse(row["states"]["path_blocked"]["permission_confirmed"])

    def test_recorded_hold_and_known_not_stopped_are_action_contradiction(self):
        m=moment(facts=[fact(),fact("FALSE",predicate="STOPPED",subject="ego",target=None)])
        out=self.run_sequence([m]);self.assertIn("ACTION_CONTRADICTION",out["scenes"][0]["codes"])
        self.assertEqual(out["status"],"CONTRADICTION")

    def test_retained_allow_with_unknown_current_guards_is_not_confirmed_permission(self):
        d=definition(effect="ALLOW")
        out=self.run_sequence([moment(definitions=[d]),moment(1,[],[fact("UNKNOWN")],"ENTER","e2",previous=True)])
        self.assertEqual(out["scenes"][1]["ledger"]["path_blocked"],"ACTIVE")
        self.assertFalse(out["scenes"][1]["states"]["path_blocked"]["permission_confirmed"])

    def test_can_only_visual_fact_cannot_confirm_release_but_ego_stopped_is_supported(self):
        a=moment();b=moment(1,[],[fact("FALSE")],"ENTER","e2",previous=True)
        b["frame_ids"]=["f","CAN:2"];b["current_frame_ids"]=["f"];b["current_evidence_refs"]=["f","CAN:2"]
        b["constraints"]["facts"][0]["evidence_refs"]=["CAN:2"]
        out=self.run_sequence([a,b]);self.assertEqual(out["scenes"][1]["ledger"]["path_blocked"],"ACTIVE")
        self.assertIn("EVIDENCE_MISSING",out["scenes"][1]["codes"])
        c=moment(facts=[fact(),fact(predicate="STOPPED",subject="ego",target=None)])
        c["frame_ids"]=["f","CAN:2"];c["current_evidence_refs"]=["f","CAN:2"]
        c["constraints"]["facts"][1]["evidence_refs"]=["CAN:2"]
        self.assertEqual(self.run_sequence([c])["status"],"PASS")

    def test_enter_recorded_action_requires_current_image_evidence(self):
        m=moment(action="ENTER",target="e2");m["frame_ids"]=["f","CAN:2"];m["current_evidence_refs"]=["f","CAN:2"]
        m["coc"]["observed_actions"][0]["evidence_refs"]=["CAN:2"]
        out=self.run_sequence([m]);self.assertIn("EVIDENCE_MISSING",out["scenes"][0]["codes"])

    def test_dense_200_moment_verification_serializes_inside_bounded_cpu_child(self):
        from apps.guardsynth_studio.jobs import child
        moments=[]
        for i in range(200):
            definitions=[definition(condition_id="density_"+str(j)) for j in range(i*4,i*4+4)] if i<16 else []
            m=moment(i,definitions=definitions,previous=i>0)
            fid="density_frame_"+str(i);m["frame_ids"]=[fid];m["current_evidence_refs"]=[fid]
            for e in m["coc"]["entities"]:e["evidence_refs"]=[fid]
            m["coc"]["evidence_refs"]=[fid]
            for a in m["coc"]["observed_actions"]:a["evidence_refs"]=[fid]
            for f in m["constraints"]["facts"]:f["evidence_refs"]=[fid];f["evidence_note"]="현재 프레임 "+str(i)
            moments.append(m)
        out=child("SEQ_CHECK",{"moments":moments,"catalog":{"sources":[]}})
        self.assertEqual(len(out["scenes"]),200)
        self.assertEqual(len(out["pending"]),64)
        self.assertEqual(out["status"],"PASS")
        checks=out["scenes"][-1]["verification"]["condition_checks"]
        self.assertEqual(checks["query_count"],64)
        self.assertTrue(all(q["status"]=="SAT" for q in checks["results"]))
        self.assertNotIn("core",out["scenes"][-1])
        self.assertNotIn("core",out["scenes"][-1]["verification"])

    def test_compact_verification_retains_carried_cnl_and_original_scene_text(self):
        from guard_synth.studio_grounded_sequence import render_grounded_constraints
        ms=[moment(),moment(1,[],[fact("UNKNOWN")],previous=True)]
        checked=self.run_sequence(ms)["scenes"][1]
        self.assertIn("보행자가 진입 경로를 점유함",render_grounded_constraints(checked["constraints"]))
        self.assertEqual(checked["explanation"],"기록 행동 설명")
        self.assertEqual(checked["observed_actions"],ms[1]["coc"]["observed_actions"])
