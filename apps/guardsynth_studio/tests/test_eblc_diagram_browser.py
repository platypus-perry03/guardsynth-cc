"""Browser acceptance of diagrams rendered from compiled EBLC, without model calls."""
from copy import deepcopy
import json
import unittest

from guard_synth.studio_sequence import compile_sequence, verify_compiled
from . import test_http_browser as http_browser
from .test_grounded_sequence import moment, definition, fact


class EBLCDiagramBrowserTest(unittest.TestCase):
    setUp = http_browser.HTTPTest.setUp
    tearDown = http_browser.HTTPTest.tearDown
    browser_login = http_browser.HTTPTest.browser_login

    def compiled(self, released=False, legacy=False):
        if legacy:
            from .test_sequence import scene, condition
            rows=[scene(0,items=[condition(condition_class='WORKZONE_OBSTACLE',source_refs=[])]),scene(1,items=[])]
        else:
            definitions=[definition(),definition(condition_id='second_condition',description='두 번째 경로 제약')]
            rows=[moment(definitions=definitions),moment(1,definitions=[],facts=[fact('FALSE' if released else 'UNKNOWN')],action='ENTER' if not released else 'HOLD',target='e2' if not released else None,previous=True)]
            rows[0]['coc']['entities'][0]['description']='자차'
            rows[1]['coc']['entities'][0]['description']='자차'
            rows[0]['coc']['entities'][1]['description']='횡단 보행자'
            rows[1]['coc']['entities'][1]['description']='횡단 보행자'
            rows[0]['coc']['entities'][2]['description']='횡단보도'
            rows[1]['coc']['entities'][2]['description']='횡단보도'
        for i,r in enumerate(rows):
            r['id']=self.ids[i]
            frame=self.store.moment(self.ids[i])['frame']['frame_id']
            # Match the actual fixture evidence so opening review fields stays valid.
            def evidence(v):
                if isinstance(v,dict):
                    for k,value in v.items():
                        if k in ('frame_ids','evidence_refs'):v[k]=[frame]
                        else:evidence(value)
                elif isinstance(v,list):
                    for value in v:evidence(value)
            evidence(r)
            with self.store.transaction():
                m=self.store.moment(self.ids[i])
                for kind,key in [('sequence_coc','coc'),('sequence_constraints','constraints')]:
                    self.store.install(m,kind,{**deepcopy(r[key]),'original_candidate':deepcopy(r[key]),'accepted_unchanged':True})
                self.store.save(m,'diagram fixture')
        compiled=compile_sequence(rows,{'sources':[]})
        verified=verify_compiled(compiled)
        return {'stages':{'eblc':{'job_status':'SUCCEEDED','stale':False,'result':compiled},'verification':{'job_status':'SUCCEEDED','stale':False,'result':verified}}}

    def inject(self,browser,value):
        browser.evaluate("(()=>{window.diagramFixture="+json.dumps(value)+";if(!window.diagramRealApi){window.diagramRealApi=api;api=async function(path,...args){return path.endsWith('/sequence')?window.diagramFixture:window.diagramRealApi(path,...args);};}document.dispatchEvent(new CustomEvent('studio:moment'));showStage(3);return true;})()")
        browser.wait("$('seq_diagram_content').hidden" if value['stages']['eblc'].get('stale') else "!$('seq_diagram_content').hidden")

    def test_vertical_rolling_overview_keyboard_swipe_and_narrow_layout(self):
        payload=self.compiled()
        browser=self.browser_login();self.inject(browser,payload)
        browser.wait("$('seq_diagram_position').textContent.includes('1 / 2')")
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_diagram_list button').length"),2)
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_diagram_card .eblc_flow_node').length"),4)
        text=browser.evaluate("document.querySelector('#seq_diagram_card .eblc_flow_node').textContent")
        self.assertIn('행동 주체: 자차',text)
        self.assertIn('횡단 보행자',text)
        self.assertIn('횡단보도',text)
        self.assertNotRegex(text,r'\b(?:ego|e[1-8])\b')
        self.assertEqual(browser.evaluate("document.querySelectorAll('[data-path$=\".entity_id\"]').length"),0)
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"facts[0].atom.subject_ref\"]').value"),'e1')
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"facts[0].atom.subject_ref\"]').selectedOptions[0].textContent"),'횡단 보행자')
        self.assertIn('"entity_id": "e1"',browser.evaluate("$('seq_coc_original').textContent"))
        browser.evaluate("$('seq_diagram_next').click();true")
        self.assertEqual(browser.evaluate("$('seq_diagram_card').dataset.conditionId"),'second_condition')
        browser.evaluate("$('seq_diagram_next').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));true")
        self.assertEqual(browser.evaluate("$('seq_diagram_card').dataset.conditionId"),'path_blocked')
        browser.evaluate("$('seq_diagram_card').dispatchEvent(new PointerEvent('pointerdown',{pointerType:'touch',pointerId:7,clientX:180,clientY:100,bubbles:true}));$('seq_diagram_card').dispatchEvent(new PointerEvent('pointerup',{pointerType:'touch',pointerId:7,clientX:80,clientY:110,bubbles:true}));true")
        self.assertEqual(browser.evaluate("$('seq_diagram_card').dataset.conditionId"),'second_condition')
        browser.evaluate("document.querySelector('#seq_diagram_list button').click();true")
        self.assertEqual(browser.evaluate("$('seq_diagram_card').dataset.conditionId"),'path_blocked')
        browser.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        self.assertTrue(browser.evaluate("$('seq_eblc_diagram').scrollWidth<=$('seq_eblc_diagram').clientWidth+1"))
        self.assertTrue(browser.evaluate("(()=>{const nodes=[...document.querySelectorAll('.eblc_flow_node')];return nodes.every((n,i)=>!i||n.getBoundingClientRect().top>=nodes[i-1].getBoundingClientRect().bottom);})()"))
        self.assertFalse(browser.evaluate("$('seq_eblc_text').closest('details').open"))
        self.assertEqual(browser.evaluate("document.querySelector('.eblc_diagram_result').dataset.status"),'PASS')
        self.assertEqual(self.store.objects('job'),[])

    def test_ego_is_not_displayed_as_a_path_and_stale_diagram_is_hidden(self):
        payload=self.compiled()
        payload['stages']['eblc']['result']['scenes'][0]['constraints'][0]['movement_ref']='ego'
        browser=self.browser_login();self.inject(browser,payload)
        text=browser.evaluate("document.querySelector('#seq_diagram_card .eblc_flow_node').textContent")
        self.assertNotIn('진행 경로: 자차',text)
        self.assertIn('행동 주체: 자차',text)
        m=self.store.moment(self.ids[0]);old=deepcopy(m['components']['sequence_coc']['payload'])
        from .helpers import edit
        edit(self.service,self.ids[0],'sequence_coc',{'entities':[{**e,'description':'새 설명으로 수정한 대상'} if e['entity_id']=='e1' else e for e in old['entities']]})
        payload['stages']['eblc']['stale']=True
        browser.evaluate('loadMoment('+json.dumps(self.ids[0])+').then(()=>true)')
        self.inject(browser,payload)
        self.assertTrue(browser.evaluate("$('seq_diagram_content').hidden"))
        self.assertEqual(browser.evaluate("$('seq_diagram_card').textContent"),'')
        self.assertNotIn('횡단 보행자',browser.evaluate("$('seq_eblc_text').textContent"))

    def test_carried_unknown_keeps_active_and_counterexample_opens_original_constraint(self):
        payload=self.compiled()
        browser=self.browser_login();self.inject(browser,payload)
        browser.evaluate('selectOrdinal(1).then(()=>{showStage(3);return true;})')
        browser.wait("$('seq_diagram_card').textContent.includes('이전 장면에서 이어짐')")
        text=browser.evaluate("$('seq_diagram_card').textContent")
        self.assertIn('활성 → 활성',text)
        self.assertIn('해제 근거가 확인되지 않아',text)
        self.assertIn('모순 발견',text)
        self.assertIn('횡단 보행자',text)
        browser.evaluate('showStage(4);true')
        browser.evaluate("document.querySelector('#seq_current_result [data-show-diagram=\"second_condition\"]').click();true")
        browser.wait("state.stage===3 && $('seq_diagram_card').dataset.conditionId==='second_condition'")
        browser.evaluate("document.querySelector('#seq_diagram_list [data-condition-id=\"path_blocked\"]').click();true")
        browser.evaluate("document.querySelector('#seq_diagram_card [data-diagram-edit]').click();true")
        browser.wait('state.stage===2 && state.moment.ordinal===0')
        self.assertTrue(browser.evaluate("document.activeElement.dataset.path.startsWith('new_definitions[0].')"))
        self.assertEqual(self.store.objects('job'),[])

    def test_release_stale_and_empty_do_not_claim_current_verification(self):
        payload=self.compiled(released=True)
        browser=self.browser_login();self.inject(browser,payload)
        browser.evaluate('selectOrdinal(1).then(()=>{showStage(3);return true;})')
        browser.wait("$('seq_diagram_card').textContent.includes('활성 → 해제')")
        payload['stages']['eblc']['stale']=True
        payload['stages']['verification']['stale']=True
        self.inject(browser,payload)
        self.assertIn('이전 생성 결과',browser.evaluate("$('seq_diagram_notice').textContent"))
        self.assertTrue(browser.evaluate("$('seq_diagram_content').hidden && !$('seq_eblc_raw').open"))
        self.assertEqual(browser.evaluate("$('seq_diagram_card').textContent"),'')
        self.assertEqual(browser.evaluate("document.querySelectorAll('#seq_diagram_card [data-diagram-edit]').length"),0)
        payload['stages']['eblc']['result']['scenes'][1]['constraints']=[]
        browser.evaluate("window.diagramFixture="+json.dumps(payload)+";document.dispatchEvent(new CustomEvent('studio:moment'));true")
        browser.wait("$('seq_diagram_content').hidden")
        self.assertIn('EBLC를 생성하면',browser.evaluate("$('seq_diagram_empty').textContent"))

    def test_legacy_diagram_preserves_text_and_does_not_invent_entity_or_permission(self):
        payload=self.compiled(legacy=True)
        browser=self.browser_login();self.inject(browser,payload)
        text=browser.evaluate("$('seq_diagram_card').textContent")
        self.assertIn('공사·장애물',text)
        self.assertIn('대상·관계가 구조화되지 않았습니다',text)
        self.assertIn(payload['stages']['eblc']['result']['scenes'][0]['constraints'][0]['activation'],text)
        self.assertNotIn('진입 가능',text)
        browser.evaluate('selectOrdinal(1).then(()=>{showStage(3);return true;})')
        browser.wait("$('seq_diagram_card').textContent.includes('이전 장면에서 이어짐')")
        self.assertIn('활성 → 활성',browser.evaluate("$('seq_diagram_card').textContent"))


    def test_unverified_and_verification_stale_never_show_green(self):
        payload=self.compiled()
        del payload['stages']['verification']
        browser=self.browser_login();self.inject(browser,payload)
        self.assertEqual(browser.evaluate("document.querySelector('.eblc_diagram_result').dataset.status"),'UNVERIFIED')
        self.assertIn('검증을 실행',browser.evaluate("$('seq_diagram_card').textContent"))
        payload=self.compiled()
        payload['stages']['verification']['stale']=True
        self.inject(browser,payload)
        self.assertEqual(browser.evaluate("document.querySelector('.eblc_diagram_result').dataset.status"),'STALE')
        self.assertIn('재검증 필요',browser.evaluate("$('seq_diagram_card').textContent"))
        self.assertNotIn('입력 조건 안에서 일치',browser.evaluate("$('seq_diagram_card').textContent"))
