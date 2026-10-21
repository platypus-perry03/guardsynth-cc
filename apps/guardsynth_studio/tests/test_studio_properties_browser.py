"""Real HTTP + CPU stages + Chromium property table and correction workflow."""
from copy import deepcopy
import threading
import unittest
from apps.guardsynth_studio.common import uid
from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio import sequence
from .test_grounded_sequence import moment, definition, guard
from . import test_openai_provider as providers
from . import test_http_browser as http_browser
from .helpers import edit, approve


class StudioPropertiesBrowserTest(unittest.TestCase):
    setUp=http_browser.HTTPTest.setUp
    tearDown=http_browser.HTTPTest.tearDown
    browser_login=http_browser.HTTPTest.browser_login

    def stages(self):
        for kind in ('SEQ_EBLC','SEQ_VERIFY'):
            queued=sequence.enqueue_stage(self.service,self.extraction,kind,'reviewer',uid())
            Worker(self.service).run_once();job=self.store.get(queued['job_id'],'job')
            self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
        return job

    def test_twelve_results_can_counterexample_edit_and_stale_results(self):
        video=self.store.get(self.extraction,'extraction')['video_id']
        vehicle=providers.OpenAIProviderTests.vehicle_state(self)
        for s in vehicle['samples']:s['vehicle_speed_kmh']=8.3
        self.service.attach_vehicle_state(video,0,vehicle,'reviewer',uid())
        m=moment(definitions=[definition(effect='ALLOW',actions=['HOLD'],action_target_ref=None)])
        fid=self.store.moment(self.ids[0])['frame']['frame_id']
        def replace(value):
            if isinstance(value,dict):
                if 'evidence_refs' in value:value['evidence_refs']=[fid]
                for v in value.values():replace(v)
            elif isinstance(value,list):
                for v in value:replace(v)
        replace(m)
        m['coc']['observed_actions'][0]['evidence_refs'].append('CAN:0')
        m['coc']['reason_bindings']=[{'action_index':0,'explanation_excerpt':m['coc']['explanation'],'reasons':[guard()]}]
        original=deepcopy(m['coc'])
        for kind,value in [('sequence_coc',m['coc']),('sequence_constraints',m['constraints'])]:
            edit(self.service,self.ids[0],kind,value);approve(self.service,self.ids[0],kind)
        job=self.stages();row=job['result']['scenes'][0]
        self.assertIn('CAN_ACTION_CONTRADICTION',row['codes'])
        self.assertEqual(len(row['properties']['results']),12)
        browser=self.browser_login();browser.evaluate('showStage(4);true')
        browser.wait("document.querySelectorAll('#seq_current_result [data-property-id]').length===12")
        self.assertEqual(browser.evaluate("document.querySelector('#seq_current_result [data-property-id=A4]').dataset.propertyStatus"),'FAIL')
        self.assertEqual(browser.evaluate("document.querySelector('#seq_current_result [data-property-id=A1]').dataset.propertyStatus"),'PASS')
        self.assertIn('8.3',browser.evaluate("document.querySelector('#seq_current_result [data-property-id=A4]').textContent"))
        browser.evaluate("document.querySelector('#seq_current_result [data-property-id=A4] [data-issue-link]').click();true")
        browser.wait("document.activeElement.classList.contains('review_item')")
        before=deepcopy(self.store.moment(self.ids[0]))
        self.assertIn('정지 유지',browser.evaluate('document.activeElement.textContent'))
        self.assertEqual(browser.evaluate("[...document.activeElement.querySelectorAll('[data-review-step]')].map(e=>e.dataset.reviewStep)"),['1','2','3','4'])
        self.assertIn('주행 지속',browser.evaluate("document.activeElement.querySelector('[data-review-step=\"3\"]').textContent"))
        self.assertEqual(self.store.moment(self.ids[0]),before)
        browser.evaluate("document.activeElement.querySelector('[data-accept-suggestion]').click();true")
        browser.wait("state.stage===4 && state.moment.components.sequence_coc.payload.observed_actions[0].code==='CONTINUE' && $('save_state').textContent==='저장됨'")
        self.assertFalse(browser.evaluate("$('seq_coc_fields').checkVisibility()"))
        self.assertTrue(browser.evaluate("$('seq_review_editor').checkVisibility()"))
        self.assertIn('8.3',browser.evaluate("$('seq_review_editor').querySelector('.repair_suggestion').textContent"))
        self.assertTrue(browser.evaluate("$('seq_review_editor').querySelector('.repair_suggestion button').disabled"))
        self.assertIn('수정 제안을 승인하여',browser.evaluate("$('seq_review_editor').textContent"))
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_coc']['payload']['observed_actions'][0]['code'],'CONTINUE')
        self.assertEqual(self.store.get(job['id'],'job')['result'],job['result'])
        self.assertNotIn('sequence_coc',self.store.moment(self.ids[0])['approvals'])
        browser.evaluate('showStage(4);true')
        self.assertIn('입력이 바뀌었습니다',browser.evaluate("$('seq_result_status').textContent"))
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_current_result [data-property-id]').length"),0)
        browser.evaluate("document.querySelector('[data-review-approve=sequence_coc]').click();true")
        browser.wait("!state.busy && !!state.moment.approvals.sequence_coc")
        self.assertTrue(browser.evaluate("state.moment.components.sequence_constraints.stale"))
        browser.evaluate("$('seq_resume').click();true")
        browser.wait("state.stage===2 && !state.busy")
        self.assertFalse(browser.evaluate("$('seq_approve_constraints').disabled"))
        browser.evaluate("$('seq_approve_constraints').click();true")
        browser.wait("!state.busy && !!state.moment.approvals.sequence_constraints")
        self.assertFalse(browser.evaluate("state.moment.components.sequence_constraints.stale"))
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['new_definitions'],m['constraints']['new_definitions'])
        self.assertTrue(browser.evaluate("$('seq_correction_flow').checkVisibility()"))
        self.assertEqual(browser.evaluate("$('seq_resume').textContent"),'변경 내용 검사')
        self.assertTrue(browser.evaluate("$('seq_correction_hint').hidden"))
        self.assertIn('EBLC를 생성한 뒤 검증',browser.evaluate("$('seq_revision_status').textContent"))
        self.assertFalse(browser.evaluate("$('seq_generate_eblc').disabled"))
        browser.evaluate('showStage(4);true')
        stopped=threading.Event()
        def worker():
            while not stopped.is_set():
                Worker(self.service).run_once();stopped.wait(.02)
        runner=threading.Thread(target=worker,daemon=True);runner.start()
        try:
            browser.evaluate("document.querySelector('[data-review-recheck]').click();true")
            browser.wait("!state.busy && !!document.querySelector('[data-correction-code=CAN_ACTION_CONTRADICTION][data-correction-status=NOT_REPORTED]')")
            # CAN is corrected, but the unchanged reason binding still describes HOLD.
            checked=sequence.latest_stage(self.service,self.extraction,'SEQ_VERIFY')
            self.assertEqual(next(p for p in checked['result']['scenes'][0]['properties']['results'] if p['property_id']=='A1')['status'],'UNKNOWN')
            self.assertEqual(self.store.objects('job')[-1]['kind'],'SEQ_VERIFY')
            self.assertIn('확인 항목',browser.evaluate("$('seq_generate_cnl').textContent"))
            self.assertFalse(browser.evaluate("$('seq_generate_cnl').disabled"))
            browser.evaluate("$('seq_generate_cnl').click();true")
            browser.wait("$('seq_cnl_text').textContent!=='아직 생성된 CNL이 없습니다.'")
            browser.wait('!state.busy')
        finally:
            stopped.set();runner.join(timeout=10)
        revised=sequence.latest_stage(self.service,self.extraction,'SEQ_VERIFY')
        self.assertNotIn('CAN_ACTION_CONTRADICTION',revised['result']['scenes'][0]['codes'])
        self.assertEqual([j['kind'] for j in self.store.objects('job')],['SEQ_EBLC','SEQ_VERIFY','SEQ_EBLC','SEQ_VERIFY','SEQ_CNL'])
        self.assertEqual(sequence.latest_stage(self.service,self.extraction,'SEQ_EBLC')['inputs']['snapshot']['moments'][0]['components']['sequence_coc']['payload']['observed_actions'][0]['code'],'CONTINUE')
        self.assertEqual(browser.evaluate("document.querySelector('#seq_current_result [data-property-id=A4]').dataset.propertyStatus"),'PASS')
        self.assertTrue(browser.evaluate("$('seq_correction_flow').hidden"))
        self.assertEqual(self.store.get(job['id'],'job')['result'],job['result'])
        self.assertEqual(m['coc'],original)
        self.assertFalse(any(j['kind'] in ('SEQ_COC','SEQ_CONSTRAINTS') for j in self.store.objects('job')))
        # Prior findings belong to collapsed, scene-specific history, not current errors.
        self.assertFalse(browser.evaluate("document.querySelector('.correction_results').open"))
        self.assertFalse(browser.evaluate("document.querySelector('[data-correction-code=CAN_ACTION_CONTRADICTION]').checkVisibility()"))
        self.assertNotIn('수정 후 확인',browser.evaluate("$('seq_common_review').textContent"))
        browser.evaluate("(()=>{const d=document.querySelector('.correction_results');for(let p=d.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;d.open=true;return true;})()")
        self.assertTrue(browser.evaluate("document.querySelector('[data-correction-code=CAN_ACTION_CONTRADICTION]').checkVisibility()"))
        browser.evaluate('selectOrdinal(1).then(()=>true)')
        browser.wait("!document.querySelector('.correction_results')")
        self.assertFalse(browser.evaluate("!!document.querySelector('[data-correction-code=CAN_ACTION_CONTRADICTION]')"))
        browser.evaluate('selectOrdinal(0).then(()=>true)')
        browser.wait("!!document.querySelector('.correction_results')")
        self.assertFalse(browser.evaluate("document.querySelector('.correction_results').open"))
        browser.evaluate("document.querySelector('#pipeline_nav [data-stage=\"1\"]').click();true")
        self.assertFalse(browser.evaluate("$('seq_coc_fields').checkVisibility()"))
        self.assertIn('주행 지속',browser.evaluate("$('seq_observed_actions').textContent"))
        # Direct CoC-tab changes invalidate all displayed downstream results without reload.
        revision=self.store.moment(self.ids[0])['revision']
        browser.evaluate("(()=>{const e=$('seq_explanation');e.value='CoC 탭에서 수정한 설명';e.dispatchEvent(new Event('input',{bubbles:true}));return flush().then(()=>true);})()")
        browser.wait(f"$('seq_revision_status').dataset.savedRevision==='{revision+1}' && $('seq_correction_flow').checkVisibility() && $('seq_revision_status').textContent.includes('CoC 검토')")
        browser.evaluate("document.querySelector('#pipeline_nav [data-stage=\"4\"]').click();true")
        self.assertIn('입력이 바뀌었습니다',browser.evaluate("$('seq_result_status').textContent"))
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_current_result [data-property-id]').length"),0)
        self.assertTrue(browser.evaluate("[...document.querySelectorAll('[data-correction-status]')].every(e=>e.dataset.correctionStatus==='PENDING')"))
        self.assertEqual(browser.evaluate("$('seq_resume').textContent"),'CoC 검토하기')
        self.assertIn('CoC 검토',browser.evaluate("$('seq_revision_status').textContent"))
        self.assertTrue(browser.evaluate("$('seq_generate_eblc').disabled"))
        self.assertNotIn('현재 저장본',browser.evaluate("$('seq_correction_flow').textContent"))
        browser.evaluate("document.querySelector('#pipeline_nav [data-stage=\"5\"]').click();true")
        self.assertIn('입력이 바뀌었습니다',browser.evaluate("$('seq_cnl_text').textContent"))
        self.assertTrue(self.store.moment(self.ids[0])['components']['sequence_constraints']['stale'])
        self.assertEqual(len(self.store.objects('job')),5)

    def test_reason_binding_editor_preserves_model_completion_window(self):
        m=moment(definitions=[definition(expected_postconditions=[guard()],postcondition_window='NEXT_OBSERVATION')]);fid=self.store.moment(self.ids[0])['frame']['frame_id']
        for e in m['coc']['entities']:e['evidence_refs']=[fid]
        m['coc']['evidence_refs']=[fid];m['coc']['observed_actions'][0]['evidence_refs']=[fid]
        m['constraints']['facts'][0]['evidence_refs']=[fid]
        edit(self.service,self.ids[0],'sequence_coc',m['coc']);edit(self.service,self.ids[0],'sequence_constraints',m['constraints'])
        browser=self.browser_login();browser.evaluate('showStage(1);true')
        browser.evaluate("[...document.querySelectorAll('#seq_coc_fields button')].find(b=>b.textContent==='이유 연결 추가').click();true")
        browser.wait("!!document.querySelector('[data-path=\"reason_bindings[0].action_index\"]')")
        browser.evaluate('flush().then(()=>true)')
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_coc']['payload']['reason_bindings'][0]['action_index'],0)
        browser.evaluate('showStage(2);true')
        browser.wait("!!document.querySelector('[data-path=\"new_definitions[0].description\"]')")
        self.assertFalse(browser.evaluate("!!document.querySelector('[data-path=\"new_definitions[0].postcondition_window\"]')"))
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"new_definitions[0].description\"]');e.value='검토한 조건 설명';e.dispatchEvent(new Event('input',{bubbles:true}));return flush().then(()=>true);})()")
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['new_definitions'][0]['postcondition_window'],'NEXT_OBSERVATION')


if __name__=='__main__':unittest.main()
