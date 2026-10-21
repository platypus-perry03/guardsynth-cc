"""Behavioral acceptance tests for recorded CoC and persistent obligations."""
from copy import deepcopy
import unittest
from guard_synth.studio_sequence import verify_sequence, validate_candidate

CATALOG = {"sources": [{"id": "yield", "text": "Yield before entering a conflicting path", "locator": "test policy 1", "reviewed": True, "expected_actions": ["ENTER"]}]}

def condition(truth="TRUE", evidence=True, **changes):
    value = {"condition_id": "pedestrian_path", "scope_id": "junction_1", "description": "보행자와 진입 경로가 겹침", "actions": ["ENTER"], "effect": "FORBID", "activation": "보행자 경로 충돌 확인", "hold": "충돌 해소 확인 전", "release": "보행자가 경로 밖으로 나감을 확인", "source_refs": ["yield"], "truth": truth, "scope_state": "IN_SCOPE", "evidence_refs": ["f"] if evidence else [], "evidence_note": "영상 확인" if evidence else ""}
    value.update(changes)
    return value

def scene(i, items=None, actions=None, reviewed=True):
    return {"id": "m"+str(i), "ordinal": i, "t0_us": i*1000000, "frame_ids": ["f"], "reviewed": reviewed, "coc": {"observations": "장면 관찰", "observed_actions": actions or ["HOLD"], "explanation": "보행자 때문에 대기함", "unknowns": "", "evidence_refs": ["f"]}, "constraints": {"constraints": items or []}}

class SequenceCheckTest(unittest.TestCase):
    def test_legacy_classification_is_optional_validated_and_does_not_change_smt(self):
        original=condition()
        validate_candidate('SEQ_CONSTRAINTS',{'constraints':[original]},{'f'},{'yield'})
        expected=verify_sequence([scene(0,[original])],CATALOG)
        for classification in ['TRAFFIC_CONTROL','VEHICLE','VULNERABLE_ROAD_USER','ROAD_LAYOUT','WORKZONE_OBSTACLE','ROAD_SURFACE','VISIBILITY',None]:
            tagged=condition(condition_class=classification)
            validate_candidate('SEQ_CONSTRAINTS',{'constraints':[tagged]},{'f'},{'yield'})
            actual=verify_sequence([scene(0,[tagged])],CATALOG)
            self.assertEqual(actual['scenes'][0]['codes'],expected['scenes'][0]['codes'])
            self.assertEqual(actual['scenes'][0]['verification']['core'],expected['scenes'][0]['verification']['core'])
            self.assertEqual([(q['query_id'],q['status']) for q in actual['scenes'][0]['verification']['smt']['results']],[(q['query_id'],q['status']) for q in expected['scenes'][0]['verification']['smt']['results']])
        with self.assertRaises(ValueError):
            validate_candidate('SEQ_CONSTRAINTS',{'constraints':[condition(condition_class='UNKNOWN_CLASS')]},{'f'},{'yield'})

    def test_three_missing_observations_do_not_erase_active_obligation(self):
        out = verify_sequence([scene(0,[condition()]),scene(1),scene(2,[condition("UNKNOWN")]),scene(3,actions=["ENTER"])],CATALOG)
        self.assertIn("ACTION_CONTRADICTION",out["scenes"][3]["codes"])
        self.assertNotIn("ACTION_CONTRADICTION",out["scenes"][3]["point_codes"])
        self.assertEqual(out["pairs"][2]["carried_ids"],["pedestrian_path"])
        self.assertEqual(out["pending"][0]["state"],"ACTIVE")
    def test_false_without_evidence_is_not_release_but_confirmed_false_is(self):
        bad=verify_sequence([scene(0,[condition()]),scene(1,[condition("FALSE",False)], ["ENTER"])],CATALOG)
        self.assertIn("ACTION_CONTRADICTION",bad["scenes"][1]["codes"])
        self.assertIn("EVIDENCE_MISSING",bad["scenes"][1]["codes"])
        good=verify_sequence([scene(0,[condition()]),scene(1,[condition("FALSE")],["ENTER"])],CATALOG)
        self.assertNotIn("ACTION_CONTRADICTION",good["scenes"][1]["codes"])
        self.assertEqual(good["pending"],[])
    def test_reactivation_and_grounded_scope_end(self):
        out=verify_sequence([scene(0,[condition()]),scene(1,[condition("FALSE")]),scene(2,[condition()],["ENTER"])],CATALOG)
        self.assertIn("ACTION_CONTRADICTION",out["scenes"][2]["codes"])
        ended=verify_sequence([scene(0,[condition()]),scene(1,[condition(scope_state="ENDED")],["ENTER"])],CATALOG)
        self.assertEqual(ended["pending"],[])
        self.assertNotIn("ACTION_CONTRADICTION",ended["scenes"][1]["codes"])
    def test_rule_conflict_does_not_poison_later_scene(self):
        other=condition(condition_id="must_enter",effect="REQUIRE")
        out=verify_sequence([scene(0,[condition(),other]),scene(1,[condition("FALSE"),condition("FALSE",condition_id="must_enter",effect="REQUIRE")],["ENTER"])],CATALOG)
        self.assertIn("RULE_CONTRADICTION",out["scenes"][0]["codes"])
        self.assertNotIn("RULE_CONTRADICTION",out["scenes"][1]["codes"])
        self.assertFalse(out["scene_truth_certified"])
    def test_identity_drift_and_empty_unreviewed_outputs_are_held(self):
        out=verify_sequence([scene(0,[condition()]),scene(1,[condition(description="다른 차량 규칙")],["ENTER"])],CATALOG)
        self.assertIn("IDENTITY_CONFLICT",out["scenes"][1]["codes"])
        for catalog, moment in [(CATALOG,scene(0,reviewed=False)),({"sources":[]},scene(0))]:
            self.assertEqual(verify_sequence([moment],catalog)["status"],"REVIEW_REQUIRED")
    def test_released_scope_need_not_be_repeated_and_action_coverage_is_specific(self):
        new=condition(condition_id="new_path",scope_id="junction_2")
        out=verify_sequence([scene(0,[condition()]),scene(1,[condition("FALSE",scope_state="ENDED")]),scene(2,[new])],CATALOG)
        self.assertNotIn("EVIDENCE_MISSING",out["scenes"][2]["codes"])
        wrong=verify_sequence([scene(0,[condition(actions=["HOLD"],truth="FALSE")],["ENTER"])],CATALOG)
        self.assertIn("POSSIBLE_OMISSION",wrong["scenes"][0]["codes"])
    def test_false_clearance_is_not_scope_expiration_and_identity_lists_are_sets(self):
        out=verify_sequence([scene(0,[condition("FALSE")]),scene(1,[condition(condition_id="other",scope_id="junction_2")],["ENTER"])],CATALOG)
        self.assertIn("EVIDENCE_MISSING",out["scenes"][1]["codes"])
        same=verify_sequence([scene(0,[condition(actions=["ENTER","START"])]),scene(1,[condition(actions=["START","ENTER"])])],CATALOG)
        self.assertNotIn("IDENTITY_CONFLICT",same["scenes"][1]["codes"])
    def test_ended_scope_does_not_cover_rule_in_later_scope(self):
        closed=condition(scope_state="ENDED")
        later=condition(condition_id="unrelated",scope_id="junction_2",actions=["HOLD"],truth="FALSE")
        out=verify_sequence([scene(0,[closed]),scene(1,[later],["ENTER"])],CATALOG)
        self.assertIn("POSSIBLE_OMISSION",out["scenes"][1]["codes"])
    def test_condition_specific_smt_identifies_the_violated_condition(self):
        out=verify_sequence([scene(0,[condition(),condition(condition_id="clear_path",truth="FALSE")],["ENTER"])],CATALOG)
        checks=out["scenes"][0]["verification"]["condition_checks"]["results"]
        self.assertEqual({r["query_id"]:r["status"] for r in checks},{"condition_pedestrian_path":"UNSAT","condition_clear_path":"SAT"})

    def test_dense_200_moment_check_fits_cpu_child_and_keeps_diagnostics(self):
        from apps.guardsynth_studio.jobs import child
        moments=[]
        for i in range(200):
            ids=range((i%4)*16,(i%4+1)*16)
            items=[condition(condition_id="condition_"+str(n),actions=["HOLD"],effect="REQUIRE",evidence_refs=["f"+str(i)],evidence_note="시점 "+str(i)) for n in ids]
            m=scene(i,items);m["frame_ids"]=["f"+str(i)];m["coc"]["evidence_refs"]=m["frame_ids"];moments.append(m)
        out=child("SEQ_CHECK",{"moments":moments,"catalog":CATALOG})
        self.assertEqual(len(out["scenes"]),200)
        self.assertEqual(len(out["pairs"]),199)
        self.assertEqual(out["scenes"][-1]["verification"]["condition_checks"]["query_count"],64)
        self.assertTrue(all(q["status"]=="SAT" for q in out["scenes"][-1]["verification"]["condition_checks"]["results"]))

    def test_rule_coverage_unknown_source_and_future_evidence(self):
        out=verify_sequence([scene(0,actions=["ENTER"])],CATALOG)
        self.assertIn("POSSIBLE_OMISSION",out["scenes"][0]["codes"])
        for change in [{"evidence_refs":["future"]},{"source_refs":["invented"]},{"actions":["ENTER","ENTER"]},{"scope_id":"   "}]:
            with self.assertRaises(ValueError):
                validate_candidate("SEQ_CONSTRAINTS",{"constraints":[condition(**change)]},{"f"},{"yield"})

from tempfile import TemporaryDirectory
from apps.guardsynth_studio.common import StudioError, uid
from apps.guardsynth_studio.jobs import Worker
from .helpers import fixture, edit, approve
from apps.guardsynth_studio.sequence import catalog_edit, sequence_view, enqueue_check, sequence_export

class SequenceWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store,self.service,self.ids,self.extraction,self.video,_=fixture(self.temp.name,2)
        self.addCleanup(self.store.close)
        catalog_edit(self.service,self.extraction,0,CATALOG,"reviewer",uid())
    def fill(self,index=0):
        identity=self.ids[index];frame=self.store.moment(identity)["frame"]["frame_id"]
        coc=scene(index)["coc"];coc["evidence_refs"]=[frame]
        edit(self.service,identity,"sequence_coc",coc);approve(self.service,identity,"sequence_coc")
        c=condition();c["evidence_refs"]=[frame]
        edit(self.service,identity,"sequence_constraints",{"constraints":[c]});approve(self.service,identity,"sequence_constraints")
        return identity
    def test_check_is_bound_to_all_revisions_and_export_is_draft(self):
        self.fill(0);self.fill(1)
        j=enqueue_check(self.service,self.extraction,"reviewer",uid());Worker(self.service).run_once()
        self.assertEqual(self.store.get(j["job_id"],"job")["status"],"SUCCEEDED")
        out=sequence_export(self.service,self.extraction)
        self.assertFalse(out["training_eligible"])
        self.assertEqual(len(out["samples"]),2)
        self.assertEqual(out["verification"]["pairs"][0]["carried_ids"],["pedestrian_path"])
        edit(self.service,self.ids[0],"sequence_coc",{"explanation":"작성자 교정"})
        self.assertTrue(sequence_view(self.service,self.extraction)["stale"])
        with self.assertRaises(StudioError): sequence_export(self.service,self.extraction)
        self.assertFalse(self.store.approved(self.store.moment(self.ids[0]),"sequence_constraints"))
    def test_catalog_cas_and_prior_changes_invalidate_later_constraints(self):
        self.fill(0);self.fill(1)
        with self.assertRaises(StudioError): catalog_edit(self.service,self.extraction,0,CATALOG,"reviewer",uid())
        edit(self.service,self.ids[0],"sequence_coc",{"explanation":"다시 검토"})
        self.service.refresh_tool_versions(self.store.moment(self.ids[1]))
        m=self.service.moment(self.ids[1])
        self.assertTrue(m["components"]["sequence_constraints"]["stale"])
    def test_changed_verifier_version_invalidates_current_export(self):
        from unittest.mock import patch
        self.fill(0);enqueue_check(self.service,self.extraction,"reviewer",uid());Worker(self.service).run_once()
        with patch("guard_synth.studio_sequence.VERSION","studio-sequential-coc-v0.2"):
            self.assertTrue(sequence_view(self.service,self.extraction)["stale"])
            with self.assertRaises(StudioError): sequence_export(self.service,self.extraction)
    def test_snapshot_change_during_queued_check_prevents_publication(self):
        self.fill(0);j=enqueue_check(self.service,self.extraction,"reviewer",uid())
        catalog_edit(self.service,self.extraction,1,{"sources":[]},"reviewer",uid())
        Worker(self.service).run_once()
        self.assertEqual(self.store.get(j["job_id"],"job")["status"],"STALE_RESULT")
        with self.assertRaises(StudioError):sequence_export(self.service,self.extraction)

from . import test_openai_provider as provider_tests
response=provider_tests.response
from apps.guardsynth_studio.sequence import generation_context
import json

class SequenceProviderTest(unittest.TestCase):
    setUp=provider_tests.OpenAIProviderTests.setUp
    connect=provider_tests.OpenAIProviderTests.connect
    run_job=provider_tests.OpenAIProviderTests.run_job
    def basic(self,index=1):
        from .test_grounded_workflow import GroundedProviderTest
        coc=GroundedProviderTest.rich(self,index,"HOLD")["coc"]
        coc["explanation"]="보행자 때문에 대기함"
        return coc
    def rich(self,index=1,action="HOLD"):
        from .test_grounded_workflow import GroundedProviderTest
        return GroundedProviderTest.rich(self,index,action)
    def grounded_constraints(self,index=1):
        value=self.rich(index)["constraints"]
        value["new_definitions"][0]["source_refs"]=["yield"]
        return value
    def test_two_stage_causal_wire_inputs_acceptance_and_budget(self):
        self.connect();catalog_edit(self.service,self.extraction,0,CATALOG,"reviewer",uid());self.reply=response(self.basic())
        self.assertEqual(self.run_job("SEQ_COC",1)["status"],"SUCCEEDED")
        with self.assertRaises(StudioError): approve(self.service,self.ids[1],"sequence_coc")
        edit(self.service,self.ids[1],"sequence_coc",{"accepted_unchanged":True});approve(self.service,self.ids[1],"sequence_coc")
        c=condition();c["evidence_refs"]=self.basic()["evidence_refs"]
        self.reply=response(self.grounded_constraints())
        self.assertEqual(self.run_job("SEQ_CONSTRAINTS",1)["status"],"SUCCEEDED")
        sent=json.loads(self.sent[1]["input"][0]["content"][0]["text"])
        self.assertEqual(sent["data"]["coc"]["explanation"],"보행자 때문에 대기함")
        self.assertEqual(len(sent["frames"]),2)
        self.assertTrue(all(f["timestamp_us"]<=1000000 for f in sent["frames"]))
        self.assertEqual(sent["data"]["catalog"]["sources"][0]["id"],"yield")
        self.assertEqual(self.service.capabilities()["call_budget"]["used"],2)
        original=self.store.moment(self.ids[1])["components"]["sequence_coc"]["payload"]["original_candidate"]
        edit(self.service,self.ids[1],"sequence_coc",{"explanation":"작성자 교정"})
        self.assertEqual(self.store.moment(self.ids[1])["components"]["sequence_coc"]["payload"]["original_candidate"],original)
    def test_fabricated_source_is_not_published_and_no_auto_retry(self):
        self.connect();edit(self.service,self.ids[1],"sequence_coc",self.basic());approve(self.service,self.ids[1],"sequence_coc")
        c=condition(source_refs=["invented"]);c["evidence_refs"]=self.basic()["evidence_refs"]
        value=self.rich(1)["constraints"];value["new_definitions"][0]["source_refs"]=["invented"]
        self.reply=response(value)
        job=self.run_job("SEQ_CONSTRAINTS",1)
        self.assertEqual(job["status"],"FAILED")
        self.assertNotIn("sequence_constraints",self.store.moment(self.ids[1])["components"])
        self.assertEqual(len(self.sent),1)
    def test_changed_catalog_before_send_spends_no_call(self):
        self.connect();edit(self.service,self.ids[1],"sequence_coc",self.basic());approve(self.service,self.ids[1],"sequence_coc")
        j=self.service.enqueue(self.ids[1],self.store.moment(self.ids[1])["revision"],"SEQ_CONSTRAINTS","reviewer",uid())
        catalog_edit(self.service,self.extraction,0,CATALOG,"reviewer",uid())
        Worker(self.service).run_once()
        self.assertEqual(self.store.get(j["job_id"],"job")["status"],"FAILED")
        self.assertEqual(len(self.sent),0)
        self.assertEqual(self.service.capabilities()["call_budget"]["used"],0)

    def test_both_stages_send_bound_causal_can(self):
        self.connect()
        vehicle=provider_tests.OpenAIProviderTests.vehicle_state(self)
        self.service.attach_vehicle_state(self.video,0,vehicle,"reviewer",uid())
        self.reply=response(self.basic(6))
        self.assertEqual(self.run_job("SEQ_COC",6)["status"],"SUCCEEDED")
        edit(self.service,self.ids[6],"sequence_coc",{"accepted_unchanged":True});approve(self.service,self.ids[6],"sequence_coc")
        self.reply=response({"new_definitions":[],"facts":[],"unresolved_previous_condition_refs":[],"unknowns":[]})
        self.assertEqual(self.run_job("SEQ_CONSTRAINTS",6)["status"],"SUCCEEDED")
        for wire in self.sent:
            data=json.loads(wire["input"][0]["content"][0]["text"])["data"]
            self.assertIn("vehicle_state",data)
            self.assertTrue(all(f["sample"] is None or f["sample"]["timestamp_us"]<=f["frame_timestamp_us"]<=6000000 for f in data["vehicle_state"]["frames"]))
