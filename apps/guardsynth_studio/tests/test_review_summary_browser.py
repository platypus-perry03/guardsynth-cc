"""Actual API/CPU pipeline regression for the reported 21-scene repeated warnings."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from apps.guardsynth_studio import sequence
from apps.guardsynth_studio.common import uid
from apps.guardsynth_studio.jobs import Worker
from . import test_http_browser as http_browser
from .helpers import fixture
from .test_sequence import scene,condition


class ReviewSummaryBrowserTest(unittest.TestCase):
    def setUp(self):
        with patch.object(http_browser,'fixture',side_effect=lambda root:fixture(root,21)):
            http_browser.HTTPTest.setUp(self)
    tearDown=http_browser.HTTPTest.tearDown
    browser_login=http_browser.HTTPTest.browser_login

    def prepare(self,actions=None,original_actions=None):
        mid=self.ids[10];frame=self.store.moment(mid)['frame']['frame_id']
        coc=scene(10)['coc'];coc['evidence_refs']=[frame];coc['observed_actions']=actions or []
        original_coc=deepcopy(coc)
        if original_actions is not None:original_coc['observed_actions']=original_actions
        con={'constraints':[condition(truth='UNKNOWN',scope_state='UNKNOWN',source_refs=[],condition_class='TRAFFIC_CONTROL',description='신호가 자차 경로에 적용되는지',evidence_refs=[frame],evidence_note='신호 적용성을 확인하지 못함')]}
        with self.store.transaction():
            m=self.store.moment(mid)
            for kind,payload in [('sequence_coc',coc),('sequence_constraints',con)]:
                self.store.install(m,kind,{**deepcopy(payload),'original_candidate':deepcopy(original_coc if kind=='sequence_coc' else payload),'accepted_unchanged':True})
                self.store.record_approval(m,kind,'APPROVE','synthetic fixture')
            self.store.save(m,'synthetic fixture')
        for kind in ['SEQ_EBLC','SEQ_VERIFY']:
            j=sequence.enqueue_stage(self.service,self.extraction,kind,'fixture',uid())
            Worker(self.service).run_once()
            result=self.store.get(j['job_id'],'job')
            self.assertEqual(result['status'],'SUCCEEDED',result.get('error'))
        self.original_coc=original_coc;self.original_con=deepcopy(con)
        return result

    def test_report_groups_21_scenes_and_20_pairs_and_keeps_source_notice_once(self):
        job=self.prepare();raw=deepcopy(job['result'])
        browser=self.browser_login();browser.evaluate('showStage(4);true')
        browser.wait("$('seq_scope_status').textContent.includes('작성된 시점 1/21개')")
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_common_review .review_common_notice').length"),1)
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_scene_results .scene_result').length"),3)
        self.assertEqual(browser.evaluate("$('seq_pair_rows').children.length"),2)
        self.assertIn('작성·검토 대기',browser.evaluate("$('seq_pair_rows').textContent"))
        self.assertIn('신호가 자차 경로에 적용되는지',browser.evaluate("$('seq_current_result').textContent"))
        self.assertIn('자차 행동이 비어',browser.evaluate("$('seq_current_result').textContent"))
        self.assertNotIn('규칙 원문이 연결되지 않았습니다.',browser.evaluate("$('seq_scene_results').textContent+$('seq_pair_rows').textContent"))
        self.assertNotIn('검사 21개',browser.evaluate("$('seq_quality').textContent"))
        self.assertEqual(self.store.get(job['id'],'job')['result'],raw)
        browser.evaluate('selectOrdinal(0).then(()=>{showStage(4);return true;})')
        browser.wait("$('seq_current_result').textContent.includes('작성 대기')")
        self.assertNotIn('모순 없음',browser.evaluate("$('seq_current_result').textContent"))
        self.assertNotIn('확인 필요',browser.evaluate("$('seq_current_result').textContent"))
        self.assertEqual([j['kind'] for j in self.store.objects('job')],['SEQ_EBLC','SEQ_VERIFY'])

    def test_empty_action_source_shows_input_guidance_and_keeps_populated_original(self):
        job=self.prepare(original_actions=['CONTINUE','ENTER']);raw=deepcopy(job['result'])
        browser=self.browser_login();browser.evaluate('showStage(4);true')
        browser.wait("!!document.querySelector('#seq_current_result [data-code=\"MISSING_OBSERVED_ACTION\"] .review_source')")
        missing="#seq_current_result [data-code=\"MISSING_OBSERVED_ACTION\"] .review_source"
        populated="#seq_current_result [data-code=\"EVIDENCE_MISSING\"] .review_source"
        self.assertEqual(browser.evaluate(f"document.querySelector({missing!r}).querySelectorAll('details,pre').length"),0)
        self.assertIn('CoC 설명과 별도로',browser.evaluate(f"document.querySelector({missing!r}).textContent"))
        self.assertNotIn('별도로 확인할 근거 필요',browser.evaluate(f"document.querySelector({missing!r}).textContent"))
        self.assertEqual(browser.evaluate(f"document.querySelector({missing!r}).querySelector('button').textContent"),'실제 행동 입력')
        self.assertEqual(browser.evaluate(f"JSON.parse(document.querySelector({populated!r}).querySelector('pre').textContent)"),self.original_con['constraints'][0])
        self.assertIn('검사에 사용한 원문 보기',browser.evaluate(f"document.querySelector({populated!r}).textContent"))
        self.assertEqual(self.store.get(job['id'],'job')['result'],raw)
        saved=self.store.moment(self.ids[10])['components']['sequence_coc']['payload']
        self.assertEqual(saved['observed_actions'],[])
        self.assertEqual(saved['original_candidate'],self.original_coc)
        self.assertEqual(saved['original_candidate']['observed_actions'],['CONTINUE','ENTER'])
        browser.evaluate(f"document.querySelector({missing!r}).querySelector('button').click();true")
        browser.wait("state.stage===4 && document.activeElement.dataset.path==='observed_actions'")

    def test_missing_action_and_signal_observation_open_editable_fields_preserve_original(self):
        self.prepare()
        browser=self.browser_login();browser.evaluate('showStage(4);true')
        browser.wait("!!document.querySelector('#seq_current_result [data-code=\"EVIDENCE_MISSING\"] button')")
        browser.evaluate("document.querySelector('#seq_current_result [data-code=\"EVIDENCE_MISSING\"] .review_source button').click();true")
        browser.wait("state.stage===4 && document.activeElement.dataset.path==='constraints[0].scope_state'")
        self.assertEqual(browser.evaluate('document.activeElement.value'),'UNKNOWN')
        browser.evaluate('showStage(4);true')
        browser.evaluate("document.querySelector('#seq_current_result [data-code=\"MISSING_OBSERVED_ACTION\"] .review_source button').click();true")
        browser.wait("state.stage===4 && document.activeElement.dataset.path==='observed_actions'")
        browser.evaluate("(()=>{const e=document.activeElement;for(const o of e.options)o.selected=o.value==='CONTINUE';e.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        m=self.store.moment(self.ids[10]);saved=m['components']['sequence_coc']['payload']
        self.assertEqual(saved['observed_actions'],['CONTINUE'])
        self.assertEqual(saved['original_candidate'],self.original_coc)
        self.assertEqual(m['components']['sequence_constraints']['payload']['original_candidate'],self.original_con)
        self.assertNotIn('sequence_coc',m['approvals'])
        browser.evaluate('showStage(4);true')
        self.assertIn('입력이 바뀌었습니다',browser.evaluate("$('seq_result_status').textContent"))
        self.assertEqual([j['kind'] for j in self.store.objects('job')],['SEQ_EBLC','SEQ_VERIFY'])



    def test_reported_sign_workzone_issue_is_unified_and_unknown_does_not_repair_type(self):
        from .test_grounded_sequence import moment, fact
        mid=self.ids[10];fid=self.store.moment(mid)['frame']['frame_id'];value=moment(10,definitions=[],facts=[],action='CONTINUE')
        value['coc']['entities'][2]['description']='바리케이드로 분리된 공사 구역'
        value['constraints']['facts']=[fact('FALSE',predicate='STOPPED',subject='ego',target=None) for _ in range(10)]+[fact('FALSE',predicate='APPLIES_TO',subject='e2',target='ego')]
        value['constraints']['facts'][10]['evidence_note']='우측의 GIVE WAY 표지가 자차 현재 차로에 적용되는지는 영상만으로 확정하기 어렵다.'
        def frames(v):
            if isinstance(v,dict):
                if 'evidence_refs' in v:v['evidence_refs']=[fid]
                for child in v.values():frames(child)
            elif isinstance(v,list):
                for child in v:frames(child)
        frames(value);value['constraints']['facts'][10]['evidence_refs']=[self.store.moment(self.ids[9])['frame']['frame_id'],fid];original=deepcopy(value['constraints']);original['facts'][10]['truth']='UNKNOWN'
        with self.store.transaction():
            m=self.store.moment(mid)
            for kind,payload in [('sequence_coc',value['coc']),('sequence_constraints',value['constraints'])]:
                self.store.install(m,kind,{**deepcopy(payload),'original_candidate':deepcopy(original if kind=='sequence_constraints' else payload),'accepted_unchanged':kind=='sequence_coc'})
                self.store.record_approval(m,kind,'APPROVE','fixture')
            self.store.save(m,'reported sign fixture')
        def verify():
            from unittest.mock import patch
            for kind in ('SEQ_EBLC','SEQ_VERIFY'):
                # Construct a historical malformed result for the renderer;
                # production approval and compile gates remain enabled below.
                with patch('apps.guardsynth_studio.sequence.input_diagnostics',return_value={'constraint_binding':None,'format_errors':{}}):
                    j=sequence.enqueue_stage(self.service,self.extraction,kind,'fixture',uid())
                Worker(self.service).run_once();job=self.store.get(j['job_id'],'job');self.assertEqual(job['status'],'SUCCEEDED',job.get('error'))
            return job
        job=verify();raw=deepcopy(job['result']);before=deepcopy(self.store.moment(mid));browser=self.browser_login();browser.evaluate('showStage(4);true')
        browser.wait("!!document.querySelector('#seq_current_result [data-property-id=B1] [data-issue-link]')")
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_current_result [data-code=UNSUPPORTED_ATOM]').length"),1)
        self.assertEqual(browser.evaluate("document.querySelectorAll('.property_table .review_source').length"),0)
        card="#seq_current_result [data-code=UNSUPPORTED_ATOM]"
        self.assertIn('적용 여부를 확인할 대상이 잘못 연결',browser.evaluate(f"document.querySelector({card!r}).textContent"))
        self.assertIn('교통 표지 대상은 아직 지원하지 않아',browser.evaluate(f"document.querySelector({card!r}).textContent"))
        self.assertEqual(browser.evaluate(f"JSON.parse(document.querySelector({card!r}).querySelector('pre').textContent)"),value['constraints']['facts'][10])
        self.assertEqual(browser.evaluate(f"[...document.querySelector({card!r}).querySelectorAll('[data-review-step]')].map(e=>e.querySelector('h4').textContent)"),['1. 검사한 내용과 근거의 출처','2. 문장의 의미와 문제','3. 수정 제안','4. 수정 승인 또는 직접 편집'])
        self.assertIn(value['constraints']['facts'][10]['evidence_note'],browser.evaluate(f"document.querySelector({card!r}).querySelector('[data-review-step=\"1\"]').textContent"))
        self.assertNotIn('GIVE WAY',browser.evaluate(f"document.querySelector({card!r}).querySelector('.review_problem_sentence').textContent"))
        self.assertIn('GIVE WAY',browser.evaluate(f"document.querySelector({card!r}).querySelector('.review_evidence_note').textContent"))
        self.assertIn('모델 생성 원문',browser.evaluate(f"document.querySelector({card!r}).querySelector('.review_evidence_note').textContent"))
        self.assertEqual(browser.evaluate(f"[...document.querySelector({card!r}).querySelectorAll('.review_evidence_frames figure')].map(e=>e.dataset.temporalRole)"),['PREVIOUS','CURRENT'])
        self.assertIn('이전 시점 10',browser.evaluate(f"document.querySelector({card!r}).querySelector('.review_evidence_frames').textContent"))
        self.assertIn('현재 시점 11',browser.evaluate(f"document.querySelector({card!r}).querySelector('.review_evidence_frames').textContent"))
        browser.evaluate(f"document.querySelector({card!r}).querySelector('.review_evidence_frames button').click();true")
        browser.wait("$('zoom').open")
        self.assertIn(self.store.moment(self.ids[9])['frame']['asset_id'],browser.evaluate("$('zoom_image').src"))
        self.assertEqual(browser.evaluate('state.moment.ordinal'),10)
        self.assertEqual(self.store.moment(mid),before)
        browser.evaluate("$('close_zoom').click();true")
        self.assertIn('영역',browser.evaluate(f"document.querySelector({card!r}).querySelector('[data-review-step=\"2\"]').textContent"))
        self.assertIn('수정 제안: 판단할 수 없음',browser.evaluate(f"document.querySelector({card!r}).querySelector('[data-review-step=\"3\"]').textContent"))
        self.assertFalse(browser.evaluate(f"document.querySelector({card!r}).querySelector('[data-review-step=\"3\"]').checkVisibility()"))
        self.assertTrue(browser.evaluate(f"document.querySelector({card!r}).querySelector(':scope > p').checkVisibility()"))
        self.assertEqual(browser.evaluate(f"document.querySelector({card!r}).querySelector('[data-accept-suggestion]').textContent"),'수정 제안 승인·반영')
        self.assertEqual(browser.evaluate(f"document.querySelector({card!r}).querySelector('[data-review-suggestion]').textContent"),'직접 편집')
        browser.evaluate("document.querySelector('[data-property-id=B1] [data-issue-link]').click();true")
        browser.wait("document.activeElement.dataset.code==='UNSUPPORTED_ATOM'")
        browser.evaluate("document.activeElement.querySelector('[data-review-suggestion]').click();true")
        browser.wait("state.stage===4 && document.activeElement.dataset.path==='facts[10].truth'")
        self.assertEqual(self.store.moment(mid),before)
        self.assertEqual(browser.evaluate("[...document.activeElement.options].map(o=>o.textContent)"),['해당함','해당하지 않음','판단할 수 없음','근거 충돌'])
        self.assertEqual(browser.evaluate("document.querySelector('#seq_review_editor [data-path=\"facts[10].atom.subject_ref\"]').value"),'e2')
        browser.evaluate("(()=>{const e=document.activeElement;e.value='UNKNOWN';e.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        saved=self.store.moment(mid);payload=saved['components']['sequence_constraints']['payload']
        self.assertEqual(payload['facts'][10]['truth'],'UNKNOWN');self.assertEqual(payload['facts'][10]['atom'],original['facts'][10]['atom']);self.assertEqual(payload['original_candidate'],original)
        self.assertEqual(self.store.get(job['id'],'job')['result'],raw);self.assertNotIn('sequence_constraints',saved['approvals'])
        self.assertIn('입력이 바뀌었습니다',browser.evaluate("$('seq_result_status').textContent"))
        self.assertTrue(browser.evaluate("$('seq_review_editor').checkVisibility()"))
        self.assertTrue(browser.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').disabled"))
        browser.evaluate("(()=>{const c=document.querySelector('[data-review-accept=sequence_constraints]');c.checked=true;c.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        self.assertTrue(browser.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').disabled"))
        from apps.guardsynth_studio.common import StudioError
        from .helpers import approve
        with self.assertRaises(StudioError) as raised:approve(self.service,mid,'sequence_constraints')
        self.assertEqual(raised.exception.code,'RELATION_FORMAT')
        self.assertNotIn('sequence_constraints',self.store.moment(mid)['approvals'])
        self.assertEqual(browser.evaluate('state.stage'),4)
        with self.assertRaises(StudioError) as blocked:
            sequence.enqueue_stage(self.service,self.extraction,'SEQ_EBLC','fixture',uid())
        self.assertEqual(blocked.exception.code,'APPROVAL_REQUIRED')
        self.assertIn('UNSUPPORTED_ATOM',raw['scenes'][10]['codes'])
        self.assertEqual(self.store.moment(mid)['components']['sequence_constraints']['payload']['original_candidate'],original)
        self.assertFalse(any(j['kind'] in ('SEQ_COC','SEQ_CONSTRAINTS') for j in self.store.objects('job')))
