"""Browser checks for structured review and evidence-directed correction."""
from copy import deepcopy
import json
import unittest
import time

from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio.common import uid

from . import test_http_browser as http_browser


class GroundedBrowserTest(unittest.TestCase):
    setUp = http_browser.HTTPTest.setUp
    tearDown = http_browser.HTTPTest.tearDown
    browser_login = http_browser.HTTPTest.browser_login

    def coc_candidate(self, index=0):
        frame = self.store.moment(self.ids[index])["frame"]["frame_id"]
        value = {"entities": [
            {"entity_id": "ego", "kind": "EGO", "description": "자차", "identity_status": "NEW_LOCAL", "previous_entity_ref": None, "evidence_refs": [frame]},
            {"entity_id": "e1", "kind": "VEHICLE", "description": "왼쪽 차량", "identity_status": "NEW_LOCAL", "previous_entity_ref": None, "evidence_refs": [frame]}],
            "relations": [{"subject_ref": "e1", "predicate": "PATH_CONFLICT", "object_ref": "ego", "truth": "TRUE", "evidence_refs": [frame]}],
            "observed_actions": [{"code": "HOLD", "subject_ref": "ego", "action_target_ref": "e1", "movement_ref": None, "evidence_refs": [frame]}],
            "observations": "왼쪽에서 차량이 접근함", "explanation": "진입을 기다림", "unknowns": ["통과 순서 미확인"], "evidence_refs": [frame]}
        return value

    def install_coc(self, index=0):
        value = self.coc_candidate(index)
        with self.store.transaction():
            m = self.store.moment(self.ids[index])
            self.store.install(m, "sequence_coc", {**deepcopy(value), "original_candidate": deepcopy(value), "accepted_unchanged": True, "origin": "MOCK"})
            self.store.save(m, "test structured browser fixture")
        return value

    def install_button_pair(self):
        from .helpers import edit,approve
        from apps.guardsynth_studio.common import StudioError
        value=self.install_coc();bundle={'new_definitions':[],'facts':[],'unresolved_previous_condition_refs':[],'unknowns':[]}
        class Provider:
            mode='MOCK';model='button-test-only';fail=False
            def __init__(inner):inner.calls=[]
            def generate(inner,kind,frames,prompt,schema,limits):
                inner.calls.append(kind)
                if inner.fail:raise StudioError('TEST_FAILURE','테스트용 생성 실패')
                result=deepcopy(value if kind=='SEQ_COC' else bundle)
                return {'parsed_candidate':result,'raw_output':json.dumps(result),'model_version':inner.model,'provider_request_id':uid()}
        self.service.provider=Provider()
        approve(self.service,self.ids[0],'sequence_coc')
        edit(self.service,self.ids[0],'sequence_constraints',bundle);approve(self.service,self.ids[0],'sequence_constraints')

    def test_completed_generation_requires_rearm_without_calls_or_deleting_results(self):
        self.install_button_pair();browser=self.browser_login()
        for stage,primary,reset in [(2,'seq_generate_constraints','seq_reset_constraints'),(1,'seq_generate_coc','seq_reset_coc')]:
            browser.evaluate(f'showStage({stage});true')
            browser.wait(f'$("{primary}").disabled && !$("{reset}").disabled')
            before=deepcopy(self.store.moment(self.ids[0]));jobs=len(self.store.objects('job'));calls=len(self.service.provider.calls)
            browser.evaluate(f'$("{primary}").click();true')
            self.assertEqual(len(self.store.objects('job')),jobs)
            browser.evaluate(f'$("{reset}").click();true')
            self.assertFalse(browser.evaluate(f'$("{primary}").disabled'))
            self.assertTrue(browser.evaluate(f'$("{reset}").disabled'))
            self.assertEqual(self.store.moment(self.ids[0]),before)
            self.assertEqual(len(self.store.objects('job')),jobs)
            self.assertEqual(len(self.service.provider.calls),calls)
            self.run_button(browser,primary)
            browser.wait(f'$("{primary}").disabled && !$("{reset}").disabled')
            self.assertEqual(len(self.service.provider.calls),calls+1)
        browser.evaluate("$('seq_reset_coc').click();selectOrdinal(1).then(()=>selectOrdinal(0)).then(()=>true)")
        browser.wait("$('seq_generate_coc').disabled")
        browser.call('Page.reload');browser.wait("!!$('login_form') && document.readyState==='complete'")
        browser.wait("!$('workspace').hidden && !!state.moment")
        self.assertTrue(browser.evaluate("$('seq_generate_coc').disabled"))
        self.assertEqual(len(self.service.provider.calls),2)

    def test_completed_eblc_and_verification_rearm_and_upstream_changes(self):
        from .helpers import edit,approve
        self.install_button_pair();browser=self.browser_login()
        self.run_button(browser,'seq_generate_eblc')
        browser.wait("$('seq_generate_eblc').disabled && !$('seq_reset_eblc').disabled")
        self.run_button(browser,'seq_check')
        browser.wait("$('seq_check').disabled && !$('seq_reset_verify').disabled")
        for primary,reset in [('seq_check','seq_reset_verify'),('seq_generate_eblc','seq_reset_eblc')]:
            before=deepcopy(self.store.moment(self.ids[0]));jobs=len(self.store.objects('job'))
            browser.evaluate(f'$("{primary}").click();$("{reset}").click();true')
            self.assertEqual(len(self.store.objects('job')),jobs)
            self.assertEqual(self.store.moment(self.ids[0]),before)
            self.assertFalse(browser.evaluate(f'$("{primary}").disabled'))
            self.run_button(browser,primary)
            browser.wait(f'$("{primary}").disabled')
        browser.wait("!$('seq_check').disabled && $('seq_reset_verify').hidden")
        self.run_button(browser,'seq_check')
        browser.wait("$('seq_check').disabled")
        edit(self.service,self.ids[0],'sequence_coc',{'explanation':'검토자가 수정한 CoC'});approve(self.service,self.ids[0],'sequence_coc')
        edit(self.service,self.ids[0],'sequence_constraints',{});approve(self.service,self.ids[0],'sequence_constraints')
        browser.evaluate('selectOrdinal(0).then(()=>true)')
        browser.wait("!$('seq_generate_eblc').disabled && $('seq_reset_eblc').hidden")
        self.assertTrue(browser.evaluate("$('seq_check').disabled && $('seq_reset_verify').hidden"))
        self.assertEqual(self.service.provider.calls,[])

    def test_failed_regeneration_keeps_previous_result_and_allows_retry(self):
        self.install_button_pair();browser=self.browser_login()
        browser.wait("!$('seq_reset_coc').disabled")
        before=deepcopy(self.store.moment(self.ids[0]));self.service.provider.fail=True
        browser.evaluate("$('seq_reset_coc').click();true")
        browser.wait("!$('seq_generate_coc').disabled")
        browser.evaluate("$('seq_generate_coc').click();true")
        end=time.monotonic()+5
        while not self.store.objects('job') and time.monotonic()<end:time.sleep(.05)
        self.assertTrue(self.store.objects('job'));Worker(self.service).run_once()
        browser.wait("!state.busy && $('error').textContent.length>0")
        self.assertEqual(self.store.objects('job')[-1]['status'],'FAILED')
        self.assertEqual(self.store.moment(self.ids[0]),before)
        self.assertFalse(browser.evaluate("$('seq_generate_coc').disabled"))
        self.service.provider.fail=False;self.run_button(browser,'seq_generate_coc')
        browser.wait("$('seq_generate_coc').disabled")

    def test_coc_default_screen_stays_minimal_without_losing_structured_data(self):
        value=self.coc_candidate()
        value['reason_bindings']=[{'action_index':0,'explanation_excerpt':value['explanation'],'reasons':[{'atom':{'predicate':'PATH_CONFLICT','subject_ref':'e1','object_ref':'ego'},'expected_truth':'TRUE'}]}]
        value['action_observation_complete']=False
        with self.store.transaction():
            m=self.store.moment(self.ids[0]);self.store.install(m,'sequence_coc',{**deepcopy(value),'original_candidate':deepcopy(value),'accepted_unchanged':True});self.store.save(m,'minimal CoC fixture')
        browser=self.browser_login();browser.evaluate('showStage(1);true')
        self.assertFalse(browser.evaluate("$('seq_coc_fields').checkVisibility()"))
        self.assertEqual(browser.evaluate("[...document.querySelectorAll('[data-step=\"1\"] summary')].filter(e=>e.checkVisibility()).map(e=>e.textContent)"),['판단 근거 확인'])
        self.assertTrue(browser.evaluate("$('seq_explanation').checkVisibility() && $('seq_original_explanation').checkVisibility() && $('seq_accept_coc').checkVisibility()"))
        browser.evaluate("$('seq_explanation').value='검토자가 고친 CoC';$('seq_explanation').dispatchEvent(new Event('input'));flush().then(()=>true)")
        saved=self.store.moment(self.ids[0])['components']['sequence_coc']['payload']
        for key in ['entities','relations','observed_actions','reason_bindings','action_observation_complete','evidence_refs']:
            self.assertEqual(saved[key],value[key])
        self.assertEqual(saved['original_candidate'],value)
        browser.evaluate('selectOrdinal(1).then(()=>selectOrdinal(0)).then(()=>true)')
        self.assertFalse(browser.evaluate("$('seq_coc_fields').checkVisibility()"))
        self.assertEqual(browser.evaluate("$('seq_explanation').value"),'검토자가 고친 CoC')

    def test_seven_classes_visible_for_legacy_and_uncreated_constraints(self):
        from .test_sequence import condition
        self.install_coc()
        candidate = {'constraints':[condition(source_refs=[])]}
        with self.store.transaction():
            m = self.store.moment(self.ids[0])
            self.store.install(m,'sequence_constraints',{**deepcopy(candidate),'original_candidate':deepcopy(candidate),'accepted_unchanged':True})
            self.store.save(m,'legacy class visibility fixture')
        browser = self.browser_login()
        browser.evaluate('showStage(2);true')
        self.assertTrue(browser.evaluate("!!document.querySelector('#seq_class_overview')?.checkVisibility()"))
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_class_overview [data-condition-class]').length"),7)
        self.assertIn('분류 정보 없음',browser.evaluate("$('seq_class_status').textContent"))
        self.assertTrue(browser.evaluate("[...document.querySelectorAll('#seq_class_overview [data-condition-class]')].every(e=>e.dataset.count==='0')"))
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"constraints[0].condition_class\"]').value"),'')
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['original_candidate'],candidate)
        browser.evaluate('selectOrdinal(1).then(()=>{showStage(2);return true;})')
        self.assertTrue(browser.evaluate("$('seq_class_overview').checkVisibility()"))
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_class_overview [data-condition-class]').length"),7)
        self.assertIn('생성 전',browser.evaluate("$('seq_class_status').textContent"))

    def test_legacy_classification_saves_and_counts_without_changing_original(self):
        from .test_sequence import condition
        coc=self.install_coc()
        candidate={'constraints':[condition(source_refs=[],evidence_refs=coc['evidence_refs'])]}
        with self.store.transaction():
            m=self.store.moment(self.ids[0])
            self.store.install(m,'sequence_constraints',{**deepcopy(candidate),'original_candidate':deepcopy(candidate),'accepted_unchanged':True})
            self.store.save(m,'legacy classification fixture')
        browser=self.browser_login()
        browser.wait("!!document.querySelector('.sequence_condition textarea')")
        browser.evaluate('showStage(2);true')
        self.assertTrue(browser.evaluate("!!document.querySelector('[data-path=\"constraints[0].condition_class\"]')?.checkVisibility()"))
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"constraints[0].condition_class\"]');e.value='VULNERABLE_ROAD_USER';e.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        saved=self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']
        self.assertEqual(saved['constraints'][0]['condition_class'],'VULNERABLE_ROAD_USER')
        self.assertEqual(saved['original_candidate'],candidate)
        self.assertFalse(browser.evaluate("$('seq_accept_constraints').checked"))
        self.assertEqual(browser.evaluate("document.querySelector('#seq_class_overview [data-condition-class=\"VULNERABLE_ROAD_USER\"]').dataset.count"),'1')
        self.assertIn('미지정 0개',browser.evaluate("$('seq_class_status').textContent"))
        browser.evaluate('selectOrdinal(1).then(()=>selectOrdinal(0)).then(()=>{showStage(2);return true;})')
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"constraints[0].condition_class\"]').value"),'VULNERABLE_ROAD_USER')
        self.assertEqual(len(self.store.objects('job')),0)

    def test_constraint_class_can_be_reviewed_without_opening_details(self):
        coc=self.coc_candidate()
        coc['entities'].append({'entity_id':'e2','kind':'ZONE','description':'진입 영역','identity_status':'NEW_LOCAL','previous_entity_ref':None,'evidence_refs':coc['evidence_refs']})
        from .test_grounded_sequence import definition
        definitions=[definition(condition_id='classified',condition_class='VEHICLE'),definition(condition_id='unclassified',condition_class=None)]
        candidate={'new_definitions':definitions,'facts':[],'unresolved_previous_condition_refs':[],'unknowns':[]}
        with self.store.transaction():
            m=self.store.moment(self.ids[0])
            self.store.install(m,'sequence_coc',{**deepcopy(coc),'original_candidate':deepcopy(coc),'accepted_unchanged':True})
            self.store.install(m,'sequence_constraints',{**deepcopy(candidate),'original_candidate':deepcopy(candidate),'accepted_unchanged':True})
            self.store.save(m,'structured class visibility fixture')
        browser=self.browser_login()
        browser.wait("!!document.querySelector('[data-path=\"new_definitions[1].condition_class\"]')")
        browser.evaluate('showStage(2);true')
        self.assertTrue(browser.evaluate("document.querySelector('[data-path=\"new_definitions[1].condition_class\"]').checkVisibility()"))
        self.assertFalse(browser.evaluate("[...document.querySelectorAll('#seq_candidates .structured_group')].some(e=>e.open)"))
        self.assertEqual(browser.evaluate("document.querySelector('#seq_class_overview [data-condition-class=\"VEHICLE\"]').dataset.count"),'1')
        self.assertIn('미지정 1개',browser.evaluate("$('seq_class_status').textContent"))
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"new_definitions[1].condition_class\"]');e.value='ROAD_SURFACE';e.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        self.assertEqual(browser.evaluate("document.querySelector('#seq_class_overview [data-condition-class=\"ROAD_SURFACE\"]').dataset.count"),'1')
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['new_definitions'][1]['condition_class'],'ROAD_SURFACE')
        self.assertIsNone(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['original_candidate']['new_definitions'][1]['condition_class'])
        self.assertFalse(browser.evaluate("$('seq_accept_constraints').checked"))
        browser.evaluate('selectOrdinal(1).then(()=>selectOrdinal(0)).then(()=>{showStage(2);return true;})')
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"new_definitions[1].condition_class\"]').value"),'ROAD_SURFACE')

    def test_structured_relations_and_actions_keep_direction_and_original(self):
        self.install_coc()
        browser = self.browser_login()
        browser.wait("!!document.querySelector('[data-path=\"relations[0].object_ref\"]')")
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"relations[0].object_ref\"]').value"), "ego")
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"observed_actions[0].action_target_ref\"]').value"), "e1")
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"relations[0].object_ref\"]');e.value='e1';e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()")
        self.assertFalse(browser.evaluate("$('seq_accept_coc').checked"))
        self.assertIn("e1", browser.evaluate("$('seq_coc_original').textContent"))
        self.assertNotIn("[object Object]", browser.evaluate("$('sequence_review').textContent"))
        browser.evaluate("$('seq_explanation').value='사람이 고친 설명';$('seq_explanation').dispatchEvent(new Event('input'));flush().then(()=>true)")
        browser.evaluate("document.querySelector('[data-restore=\"sequence_coc\"]').click();flush().then(()=>true)")
        self.assertEqual(browser.evaluate("$('seq_explanation').value"),"진입을 기다림")
        self.assertFalse(browser.evaluate("$('seq_accept_coc').disabled || $('seq_accept_coc').checked"))

    def test_counterexample_opens_referenced_previous_moment_and_field(self):
        self.install_coc(0)
        self.install_coc(1)
        browser = self.browser_login()
        browser.evaluate('selectOrdinal(1).then(()=>true)')
        # Verification is CPU-only; replace only its HTTP response to exercise the real UI renderer.
        payload = {"stages": {"verification": {"job_status": "SUCCEEDED", "stale": False, "result": {
            "status": "CONTRADICTION", "scenes": [{"moment_id": self.ids[1], "ordinal": 1, "status": "CONTRADICTION", "codes": ["ACTION_CONTRADICTION"],
            "review_items": [{"code": "ACTION_CONTRADICTION", "message": "왼쪽 차량과 경로가 겹칩니다", "sources": [{"moment_id": self.ids[0], "component": "sequence_coc", "path": "/relations/0", "value": {"subject_ref": "e1", "predicate": "PATH_CONFLICT", "object_ref": "ego", "truth": "TRUE"}, "evidence_refs": [self.store.moment(self.ids[0])["frame"]["frame_id"]]}]}]}], "pairs": [], "pending": []}}},
            "quality": {"first_pass": {"total": 2, "pass": 0, "contradiction": 1, "review_required": 1, "pass_rate": 0}, "reviewed": {"total": 2, "pass": 1, "contradiction": 0, "review_required": 1, "pass_rate": 0.5}, "items": []}}
        browser.evaluate("(()=>{const prior=api;api=async function(path,...args){return path.endsWith('/sequence')?" + json.dumps(payload) + ":prior(path,...args);};document.dispatchEvent(new CustomEvent('studio:moment'));showStage(4);return true;})()")
        browser.wait("!!document.querySelector('.review_source button')")
        self.assertIn("e1", browser.evaluate("$('seq_current_result').textContent"))
        self.assertIn("50", browser.evaluate("$('seq_quality').textContent"))
        browser.evaluate("document.querySelector('.review_source button').click();true")
        browser.wait("state.moment.ordinal===0 && state.stage===4 && !$('seq_review_editor').hidden")
        self.assertEqual(browser.evaluate("document.activeElement.dataset.path"), "relations[0].truth")
        self.assertTrue(browser.evaluate("document.activeElement.checkVisibility()"))
        self.assertFalse(browser.evaluate("$('seq_coc_fields').checkVisibility()"))
        browser.evaluate("[...$('seq_review_editor').querySelectorAll('button')].find(b=>b.textContent==='수정창 닫기').click();true")
        self.assertFalse(browser.evaluate("$('seq_coc_fields').checkVisibility()"))
        browser.evaluate("$('seq_explanation').value='검토자가 수정한 문장';$('seq_explanation').dispatchEvent(new Event('input',{bubbles:true}));true")
        self.assertNotIn("50.0%", browser.evaluate("$('seq_quality').textContent"))
        self.assertIn("현재 입력의 검증 결과는 아직 없습니다", browser.evaluate("$('seq_quality').textContent"))
        self.assertIn("검증 실행 안내", browser.evaluate("$('seq_quality').textContent"))
        self.assertTrue(browser.evaluate("!!$('seq_verify_guidance').textContent.trim()"))
        self.assertIn("일치 0개 (0.0%)", browser.evaluate("$('seq_quality').textContent"))

    def run_button(self, browser, identity):
        count = len(self.store.objects("job"))
        browser.wait('!$("' + identity + '").disabled')
        browser.evaluate('$("' + identity + '").click();true')
        end = time.monotonic() + 5
        while len(self.store.objects("job")) == count and time.monotonic() < end:
            time.sleep(.05)
        self.assertGreater(len(self.store.objects("job")), count)
        Worker(self.service).run_once()
        browser.wait('!state.busy')
        job = self.store.objects("job")[-1]
        self.assertEqual(job["status"], "SUCCEEDED", job.get("error"))

    def test_generated_structured_pair_edits_round_trip_without_losing_guards(self):
        coc = self.coc_candidate()
        coc["entities"][0]["kind"] = "EGO"
        coc["entities"].append({"entity_id": "e2", "kind": "ZONE", "description": "진입 영역", "identity_status": "NEW_LOCAL", "previous_entity_ref": None, "evidence_refs": coc["evidence_refs"]})
        coc["observed_actions"][0]["action_target_ref"] = None
        conflict = {"predicate": "PATH_CONFLICT", "subject_ref": "e1", "object_ref": "ego"}
        clear = {"predicate": "PATH_CLEAR", "subject_ref": "e2", "object_ref": None}
        inside = {"predicate": "IN", "subject_ref": "ego", "object_ref": "e2"}
        bundle = {"new_definitions": [{"condition_id": "crossing_vehicle", "condition_class": "VEHICLE", "subject_ref": "ego", "condition_target_refs": ["e1"], "action_target_ref": "e2", "movement_ref": None, "description": "왼쪽 차량과 경로가 겹치면 진입 보류", "effect": "FORBID", "actions": ["ENTER"], "activation_all_of": [{"atom": conflict, "expected_truth": "TRUE"}], "release_any_of": [{"atom": conflict, "expected_truth": "FALSE"}], "preconditions": [{"atom": clear, "expected_truth": "TRUE"}], "expected_postconditions": [{"atom": inside, "expected_truth": "FALSE"}], "source_refs": []}],
            "facts": [{"atom": conflict, "truth": "TRUE", "evidence_refs": coc["evidence_refs"], "evidence_note": "왼쪽에서 차량이 접근함"}, {"atom": clear, "truth": "UNKNOWN", "evidence_refs": coc["evidence_refs"], "evidence_note": "진입 영역 전체가 보이지 않음"}], "unresolved_previous_condition_refs": [], "unknowns": ["경로가 비었는지 미확인"]}
        class Provider:
            mode = "MOCK"
            model = "test-only"
            def generate(self, kind, frames, prompt, schema, limits):
                value = deepcopy(coc if kind == "SEQ_COC" else bundle)
                return {"parsed_candidate": value, "raw_output": json.dumps(value), "model_version": "test-only", "provider_request_id": uid()}
        self.service.provider = Provider()
        browser = self.browser_login()
        self.run_button(browser, "seq_generate_coc")
        browser.evaluate('$("seq_accept_coc").click();true')
        browser.wait('!$("seq_approve_coc").disabled')
        browser.evaluate('$("seq_approve_coc").click();true')
        browser.wait('!state.busy && state.stage===2')
        self.run_button(browser, "seq_generate_constraints")
        self.assertFalse(browser.evaluate('document.querySelector("#seq_candidates .structured_group").open'))
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"new_definitions[0].description\"]');e.value='차량 경로 충돌이 끝날 때까지 진입을 기다림';e.dispatchEvent(new Event('input',{bubbles:true}));return flush().then(()=>true);})()")
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"facts[1].truth\"]');e.value='FALSE';e.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        saved = self.store.moment(self.ids[0])["components"]["sequence_constraints"]["payload"]
        self.assertEqual(saved["facts"][1]["truth"], "FALSE")
        self.assertEqual(saved["new_definitions"][0]["expected_postconditions"], [{"atom": inside, "expected_truth": "FALSE"}])
        self.assertEqual(saved["new_definitions"][0]["release_any_of"], [{"atom": conflict, "expected_truth": "FALSE"}])
        self.assertEqual(saved["new_definitions"][0]["condition_target_refs"], ["e1"])
        self.assertEqual(saved["original_candidate"]["facts"][1]["truth"], "UNKNOWN")
        self.assertFalse(browser.evaluate('$("seq_accept_constraints").checked'))
        browser.wait('!$("seq_approve_constraints").disabled')
        browser.evaluate('$("seq_approve_constraints").click();true')
        browser.wait('!state.busy && state.stage===3')
        self.run_button(browser, "seq_generate_eblc")
        browser.evaluate('showStage(4);true')
        self.run_button(browser, "seq_check")
        self.assertIn("모델 첫 제안", browser.evaluate('$("seq_quality").textContent'))
        self.assertIn("검토 후 현재 결과", browser.evaluate('$("seq_quality").textContent'))
        browser.evaluate('showStage(5);true')
        self.run_button(browser, "seq_generate_cnl")
        self.assertTrue(browser.evaluate('$("seq_cnl_text").textContent.length>0'))
        browser.evaluate('selectOrdinal(1).then(()=>selectOrdinal(0)).then(()=>true)')
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"facts[1].truth\"]').value"), "FALSE")
        self.assertFalse(browser.evaluate('$("error").textContent.length>0'))

    def test_missing_rows_can_be_added_removed_and_saved_without_regeneration(self):
        coc = self.coc_candidate()
        coc['entities'][0]['kind'] = 'EGO'
        coc['entities'].append({'entity_id':'e2','kind':'ZONE','description':'진입 영역','identity_status':'NEW_LOCAL','previous_entity_ref':None,'evidence_refs':coc['evidence_refs']})
        coc['observed_actions'] = []
        bundle = {'new_definitions':[{'condition_id':'path_check','condition_class':'VEHICLE','subject_ref':'ego','condition_target_refs':['e1'],'action_target_ref':'e2','movement_ref':None,'description':'경로가 겹치면 진입 보류','effect':'FORBID','actions':['ENTER'],'activation_all_of':[],'release_any_of':[],'preconditions':[],'expected_postconditions':[],'source_refs':[]}],'facts':[],'unresolved_previous_condition_refs':[],'unknowns':[]}
        model_atom={'predicate':'PATH_CONFLICT','subject_ref':'e1','object_ref':'ego'}
        bundle['new_definitions'][0]['activation_all_of']=[{'atom':model_atom,'expected_truth':'TRUE'}]
        bundle['new_definitions'][0]['release_any_of']=[{'atom':deepcopy(model_atom),'expected_truth':'FALSE'}]
        class Provider:
            mode = 'MOCK'
            model = 'test-only'
            def generate(self,kind,frames,prompt,schema,limits):
                value = deepcopy(coc if kind=='SEQ_COC' else bundle)
                return {'parsed_candidate':value,'raw_output':json.dumps(value),'model_version':'test-only','provider_request_id':uid()}
        self.service.provider = Provider()
        browser = self.browser_login()
        self.run_button(browser,'seq_generate_coc')
        browser.wait("!!document.querySelector('[data-add=\"observed_actions\"]')")
        browser.evaluate("document.querySelector('[data-add=\"observed_actions\"]').click();flush().then(()=>true)")
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"observed_actions[0].code\"]').value"),'HOLD')
        self.assertTrue(browser.evaluate("$('seq_accept_coc').disabled && !$('seq_accept_coc').checked"))
        for _ in range(4):
            browser.evaluate("document.querySelector('[data-add=\"observed_actions\"]').click();flush().then(()=>true)")
        self.assertTrue(browser.evaluate("document.querySelector('[data-add=\"observed_actions\"]').disabled"))
        for index in range(4,0,-1):
            browser.evaluate("document.querySelector('[data-remove=\"observed_actions["+str(index)+"]\"]').click();flush().then(()=>true)")
        self.assertFalse(browser.evaluate("document.querySelector('[data-add=\"observed_actions\"]').disabled"))
        browser.evaluate("document.querySelector('[data-add=\"entities\"]').click();flush().then(()=>true)")
        self.assertFalse(browser.evaluate("!!document.querySelector('[data-path=\"entities[3].entity_id\"]')"))
        new_entity = self.store.moment(self.ids[0])['components']['sequence_coc']['payload']['entities'][3]['entity_id']
        self.assertIn(new_entity,browser.evaluate("[...document.querySelector('[data-path=\"observed_actions[0].action_target_ref\"]').options].map(o=>o.value)"))
        browser.evaluate("document.querySelector('[data-remove=\"entities[3]\"]').click();flush().then(()=>true)")
        browser.evaluate("document.querySelector('[data-add=\"relations\"]').click();flush().then(()=>true)")
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"relations[1].truth\"]').value"),'UNKNOWN')
        browser.evaluate("document.querySelector('[data-remove=\"relations[1]\"]').click();flush().then(()=>true)")
        browser.evaluate("$('seq_approve_coc').click();true")
        browser.wait('!state.busy && state.stage===2')
        self.run_button(browser,'seq_generate_constraints')
        self.assertFalse(browser.evaluate("!!document.querySelector('[data-add=\"new_definitions\"]')"))
        self.assertFalse(browser.evaluate("!!document.querySelector('[data-path=\"new_definitions[0].condition_id\"]')"))
        browser.evaluate("document.querySelector('[data-add=\"facts\"]').click();flush().then(()=>true)")
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"facts[0].truth\"]');e.value='TRUE';e.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        browser.evaluate("document.querySelector('[data-add=\"facts\"]').click();flush().then(()=>true)")
        browser.evaluate("document.querySelector('[data-remove=\"facts[1]\"]').click();flush().then(()=>true)")
        saved = self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']
        self.assertEqual(len(saved['facts']),1)
        self.assertEqual(saved['facts'][0]['truth'],'TRUE')
        self.assertEqual(saved['new_definitions'][0]['preconditions'],[])
        self.assertEqual(saved['new_definitions'][0]['activation_all_of'],bundle['new_definitions'][0]['activation_all_of'])
        self.assertEqual(saved['original_candidate']['new_definitions'][0]['activation_all_of'],bundle['new_definitions'][0]['activation_all_of'])
        self.assertEqual(saved['original_candidate']['facts'],[])
        self.assertTrue(browser.evaluate("$('seq_accept_constraints').disabled && !$('seq_accept_constraints').checked"))
        self.assertEqual(len(self.store.objects('job')),2)
        browser.evaluate("$('seq_approve_constraints').click();true")
        browser.wait('!state.busy && state.stage===3')
        self.run_button(browser,'seq_generate_eblc')
        browser.evaluate('showStage(4);true')
        self.run_button(browser,'seq_check')
        result = self.store.objects('job')[-1]['result']['scenes'][0]
        self.assertNotIn('UNSUPPORTED_CONDITION',result['codes'])
        self.assertNotIn('UNSUPPORTED_ATOM',result['codes'])
        self.assertNotIn('UNSUPPORTED_ACTION_TARGET',result['codes'])
        browser.evaluate('showStage(2);true')
        browser.evaluate("document.querySelector('[data-remove=\"new_definitions[0]\"]').click();flush().then(()=>true)")
        browser.evaluate('selectOrdinal(1).then(()=>selectOrdinal(0)).then(()=>true)')
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"facts[0].truth\"]').value"),'TRUE')
        self.assertFalse(browser.evaluate("$('error').textContent.length>0"))
        browser.evaluate("document.querySelector('[data-restore=\"sequence_constraints\"]').click();flush().then(()=>true)")
        restored = self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']
        self.assertEqual(restored['facts'],[])
        self.assertEqual(restored['original_candidate']['facts'],[])
        self.assertFalse(browser.evaluate("$('seq_accept_constraints').disabled || $('seq_accept_constraints').checked"))

    def test_full_fact_counterexample_displays_truth_and_opens_truth_field(self):
        coc = self.install_coc()
        facts = [{'atom':{'predicate':'PATH_CONFLICT','subject_ref':'e1','object_ref':'ego'},'truth':truth,'evidence_refs':coc['evidence_refs'],'evidence_note':'차량 경로 관찰'} for truth in ['TRUE','FALSE']]
        bundle = {'new_definitions':[],'facts':facts,'unresolved_previous_condition_refs':[],'unknowns':[]}
        with self.store.transaction():
            m = self.store.moment(self.ids[0])
            self.store.install(m,'sequence_constraints',deepcopy(bundle))
            self.store.save(m,'fact counterexample browser fixture')
        browser = self.browser_login()
        payload = {'stages':{'verification':{'job_status':'SUCCEEDED','stale':False,'result':{'status':'CONTRADICTION','scenes':[{'moment_id':self.ids[0],'ordinal':0,'status':'CONTRADICTION','codes':['OBSERVATION_CONFLICT'],'review_items':[{'code':'OBSERVATION_CONFLICT','message':'같은 관계를 서로 다르게 확인함','sources':[{'moment_id':self.ids[0],'component':'sequence_constraints','path':'/facts/'+str(i),'value':f,'evidence_refs':f['evidence_refs']} for i,f in enumerate(facts)]}]}],'pairs':[],'pending':[]}}}}
        browser.evaluate("(()=>{const prior=api;api=async function(path,...args){return path.endsWith('/sequence')?"+json.dumps(payload)+":prior(path,...args);};document.dispatchEvent(new CustomEvent('studio:moment'));showStage(4);return true;})()")
        browser.wait("document.querySelectorAll('#seq_current_result .review_source button').length===2")
        visible = browser.evaluate("$('seq_current_result').textContent")
        self.assertIn('해당함',visible)
        self.assertIn('해당하지 않음',visible)
        browser.evaluate("document.querySelectorAll('#seq_current_result .review_source button')[1].click();true")
        browser.wait("state.stage===4 && !$('seq_review_editor').hidden")
        self.assertEqual(browser.evaluate('document.activeElement.dataset.path'),'facts[1].truth')
