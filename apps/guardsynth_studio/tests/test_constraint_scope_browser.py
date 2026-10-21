"""Constraint class totals and current applicability stay visibly distinct."""
from copy import deepcopy
import json
import unittest

from guard_synth.studio_sequence import compile_sequence
from . import test_grounded_browser as grounded_browser
from .test_sequence import condition
from .test_grounded_sequence import definition, fact


class ConstraintScopeBrowserTest(unittest.TestCase):
    setUp = grounded_browser.GroundedBrowserTest.setUp
    tearDown = grounded_browser.GroundedBrowserTest.tearDown
    browser_login = grounded_browser.GroundedBrowserTest.browser_login
    coc_candidate = grounded_browser.GroundedBrowserTest.coc_candidate
    install_coc = grounded_browser.GroundedBrowserTest.install_coc

    def install_constraints(self, candidate):
        with self.store.transaction():
            m = self.store.moment(self.ids[0])
            self.store.install(m, 'sequence_constraints', {**deepcopy(candidate), 'original_candidate': deepcopy(candidate)})
            self.store.save(m, 'scope browser fixture')

    def test_empty_constraints_with_legacy_coc_explain_facts_and_block_generation(self):
        from .test_sequence import scene
        legacy=scene(0)['coc'];fid=self.store.moment(self.ids[0])['frame']['frame_id'];legacy['evidence_refs']=[fid]
        with self.store.transaction():
            m=self.store.moment(self.ids[0]);self.store.install(m,'sequence_coc',legacy);self.store.save(m,'legacy empty fixture')
        predicates=['STOPPED','VISIBILITY_INSUFFICIENT','SURFACE_RISK','PATH_CLEAR','ZONE_CLOSED']
        facts=[{'atom':{'predicate':p,'subject_ref':'ego','object_ref':None},'truth':'FALSE' if i<2 else 'UNKNOWN','evidence_refs':[fid],'evidence_note':'영상에서 별도 확인 필요'} for i,p in enumerate(predicates)]
        candidate={'new_definitions':[],'facts':facts,'unresolved_previous_condition_refs':[],'unknowns':[]}
        self.install_constraints(candidate)
        browser=self.browser_login();browser.wait("!!document.querySelector('.constraint_empty_notice')")
        browser.evaluate("state.capabilities.provider_mode='REAL';state.moment.generation={enabled:true,reason:''};state.moment.approvals.sequence_coc={decision:'APPROVE',component_id:state.moment.components.sequence_coc.id};document.dispatchEvent(new CustomEvent('studio:moment'));showStage(2);true")
        browser.wait("$('seq_constraints_generation_reason').textContent.includes('장면 대상 정보')")
        self.assertTrue(browser.evaluate("$('seq_generate_constraints').disabled"))
        self.assertTrue(browser.evaluate("$('seq_back_to_coc').checkVisibility()"))
        self.assertIn('필요 없다고 판단할 수 없습니다',browser.evaluate("document.querySelector('.constraint_empty_notice').textContent"))
        self.assertIn('관찰 항목 · 5개',browser.evaluate("$('seq_candidates').textContent"))
        self.assertEqual(browser.evaluate("document.querySelectorAll('.fact_preview li').length"),5)
        self.assertEqual(browser.evaluate("[...document.querySelectorAll('.fact_preview li')].filter(e=>e.textContent.includes('대상 연결 필요')).length"),2)
        self.assertNotIn('ego ·',browser.evaluate("document.querySelector('.fact_preview').textContent"))
        browser.evaluate("$('seq_back_to_coc').click();true")
        self.assertEqual(browser.evaluate('state.stage'),1)
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['original_candidate'],candidate)
        self.assertEqual(self.store.objects('job'),[])

    def test_empty_constraints_with_entity_coc_do_not_mean_safety_pass(self):
        self.install_coc()
        self.install_constraints({'new_definitions':[],'facts':[],'unresolved_previous_condition_refs':[],'unknowns':[]})
        browser=self.browser_login();browser.wait("!!document.querySelector('.constraint_empty_notice')")
        browser.evaluate("state.capabilities.provider_mode='REAL';state.moment.generation={enabled:true,reason:''};state.moment.approvals.sequence_coc={decision:'APPROVE',component_id:state.moment.components.sequence_coc.id};document.dispatchEvent(new CustomEvent('studio:moment'));showStage(2);true")
        browser.wait("$('seq_generate_constraints').disabled && !$('seq_reset_constraints').disabled")
        browser.evaluate("$('seq_reset_constraints').click();true")
        self.assertFalse(browser.evaluate("$('seq_generate_constraints').disabled"))
        self.assertIn('안전이나 검증 통과를 뜻하지 않습니다',browser.evaluate("document.querySelector('.constraint_empty_notice').textContent"))
        self.assertFalse(browser.evaluate("$('seq_back_to_coc').checkVisibility()"))

    def test_legacy_groups_archive_and_reclassify_without_changing_original(self):
        coc = self.install_coc()
        candidate = {'constraints': [condition(condition_id='active', condition_class='WORKZONE_OBSTACLE'),
                      condition('UNKNOWN', condition_id='uncertain', condition_class='TRAFFIC_CONTROL', scope_state='UNKNOWN'),
                      condition('UNKNOWN', condition_id='ended', condition_class='VULNERABLE_ROAD_USER', scope_state='ENDED')]}
        for c in candidate['constraints']:
            c.update(evidence_refs=coc['evidence_refs'], source_refs=[])
        self.install_constraints(candidate)
        browser = self.browser_login()
        browser.wait("document.querySelectorAll('.sequence_condition').length===3")
        browser.evaluate('showStage(2);true')
        self.assertEqual(browser.evaluate("[...document.querySelectorAll('.sequence_condition')].map(e=>e.dataset.scopeStatus)"), ['ACTIVE', 'UNCERTAIN', 'NOT_ACTIVE'])
        self.assertFalse(browser.evaluate("document.querySelector('[data-scope-group=NOT_ACTIVE]').open"))
        self.assertFalse(browser.evaluate("document.querySelector('[data-condition-id=ended]').checkVisibility()"))
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=VULNERABLE_ROAD_USER]').dataset.active"), '0')
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=VULNERABLE_ROAD_USER]').dataset.inactive"), '1')
        browser.evaluate("document.querySelector('[data-scope-group=NOT_ACTIVE]').open=true;true")
        self.assertTrue(browser.evaluate("document.querySelector('[data-condition-id=ended]').checkVisibility()"))
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"constraints[0].scope_state\"]');e.value='ENDED';e.dispatchEvent(new Event('change',{bubbles:true}));return flush().then(()=>true);})()")
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-id=active]').dataset.scopeStatus"), 'NOT_ACTIVE')
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['original_candidate'], candidate)

    def test_inherited_released_definition_is_archived_and_links_to_origin(self):
        moments=[]
        for i in range(2):
            coc=self.coc_candidate(i)
            coc['entities'].append({'entity_id':'e2','kind':'ZONE','description':'횡단보도','identity_status':'NEW_LOCAL','previous_entity_ref':None,'evidence_refs':coc['evidence_refs']})
            if i:
                for e in coc['entities']:
                    e.update(identity_status='MATCHED_PREVIOUS',previous_entity_ref=e['entity_id'])
            f=fact('FALSE' if i else 'TRUE');f['evidence_refs']=coc['evidence_refs']
            candidate={'new_definitions':[] if i else [definition(condition_class='VEHICLE')], 'facts':[f], 'unknowns':[], 'unresolved_previous_condition_refs':[]}
            with self.store.transaction():
                m=self.store.moment(self.ids[i])
                self.store.install(m,'sequence_coc',{**deepcopy(coc),'original_candidate':deepcopy(coc)})
                self.store.install(m,'sequence_constraints',{**deepcopy(candidate),'original_candidate':deepcopy(candidate)})
                self.store.save(m,'inherited scope fixture')
            moments.append({'id':m['id'],'ordinal':i,'t0_us':m['t0_us'],'frame_ids':coc['evidence_refs'],'reviewed':True,'coc':coc,'constraints':candidate})
        compiled=compile_sequence(moments,{'sources':[]})
        response={'stages':{'eblc':{'job_status':'SUCCEEDED','stale':False,'result':compiled}}}
        browser=self.browser_login()
        browser.evaluate("(()=>{window.scopeBaseApi=api;api=async function(path,...args){return path.endsWith('/sequence')?"+json.dumps(response)+":scopeBaseApi(path,...args);};return selectOrdinal(1).then(()=>{showStage(2);return true;});})()")
        browser.wait("!!document.querySelector('.carried_condition')")
        self.assertEqual(browser.evaluate("document.querySelector('.carried_condition').dataset.scopeStatus"),'NOT_ACTIVE')
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=VEHICLE]').dataset.inactive"),'1')
        self.assertIn('현재 제약 0개',browser.evaluate("$('seq_class_status').textContent"))
        browser.evaluate("document.querySelector('[data-scope-group=NOT_ACTIVE]').open=true;document.querySelector('.carried_condition button').click();true")
        browser.wait('state.moment.ordinal===0 && !!document.querySelector(".review_highlight")')
        self.assertEqual(browser.evaluate('state.stage'),2)

    def test_ended_without_evidence_and_conflicting_evidence_remain_uncertain(self):
        self.install_coc()
        candidate = {'constraints': [condition('UNKNOWN', evidence=False, condition_id='ungrounded', scope_state='ENDED'),
                                    condition('CONFLICT', condition_id='conflict', scope_state='ENDED')]}
        self.install_constraints(candidate)
        browser = self.browser_login()
        browser.wait("document.querySelectorAll('.sequence_condition').length===2")
        self.assertTrue(browser.evaluate("[...document.querySelectorAll('.sequence_condition')].every(e=>e.dataset.scopeStatus==='UNCERTAIN')"))

    def test_modern_states_require_fresh_eblc_and_edit_invalidates_badges(self):
        coc = self.install_coc()
        coc['entities'].append({'entity_id': 'e2', 'kind': 'ZONE', 'description': '진입 영역', 'identity_status': 'NEW_LOCAL', 'previous_entity_ref': None, 'evidence_refs': coc['evidence_refs']})
        with self.store.transaction():
            m = self.store.moment(self.ids[0])
            self.store.install(m, 'sequence_coc', {**deepcopy(coc), 'original_candidate': deepcopy(coc)})
            self.store.save(m, 'scope entities fixture')
        d = definition(condition_class='VEHICLE')
        f = fact(subject='e1', target='e2'); f['evidence_refs'] = coc['evidence_refs']
        candidate = {'new_definitions': [d], 'facts': [f], 'unresolved_previous_condition_refs': [], 'unknowns': []}
        self.install_constraints(candidate)
        browser = self.browser_login()
        browser.wait("!!document.querySelector('[data-condition-id=path_blocked]')")
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-id=path_blocked]').dataset.scopeStatus"), 'PENDING')
        m = self.store.moment(self.ids[0])
        compiled = compile_sequence([{'id': m['id'], 'ordinal': 0, 't0_us': m['t0_us'], 'frame_ids': coc['evidence_refs'], 'reviewed': True, 'coc': coc, 'constraints': candidate}], {'sources': []})
        response = {'stages': {'eblc': {'job_status': 'SUCCEEDED', 'stale': False, 'result': compiled}}}
        browser.evaluate("(()=>{window.scopeBaseApi=api;api=async function(path,...args){return path.endsWith('/sequence')?"+json.dumps(response)+":scopeBaseApi(path,...args);};document.dispatchEvent(new CustomEvent('studio:moment'));return true;})()")
        browser.wait("document.querySelector('[data-condition-id=path_blocked]').dataset.scopeStatus==='ACTIVE'")
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=VEHICLE]').dataset.active"), '1')
        unknown=deepcopy(candidate);unknown['facts'][0]['truth']='UNKNOWN'
        unknown_compiled=compile_sequence([{'id':m['id'],'ordinal':0,'t0_us':m['t0_us'],'frame_ids':coc['evidence_refs'],'reviewed':True,'coc':coc,'constraints':unknown}],{'sources':[]})
        unknown_response={'stages':{'eblc':{'job_status':'SUCCEEDED','stale':False,'result':unknown_compiled}}}
        browser.evaluate("(()=>{api=async function(path,...args){return path.endsWith('/sequence')?"+json.dumps(unknown_response)+":scopeBaseApi(path,...args);};document.dispatchEvent(new CustomEvent('studio:moment'));return true;})()")
        browser.wait("document.querySelector('[data-condition-id=path_blocked]').dataset.scopeStatus==='UNCERTAIN'")
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=VEHICLE]').dataset.uncertain"),'1')
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=VEHICLE]').dataset.pending"),'0')
        browser.evaluate("(()=>{api=async function(path,...args){return path.endsWith('/sequence')?"+json.dumps(response)+":scopeBaseApi(path,...args);};document.dispatchEvent(new CustomEvent('studio:moment'));return true;})()")
        browser.wait("document.querySelector('[data-condition-id=path_blocked]').dataset.scopeStatus==='ACTIVE'")
        browser.evaluate("(()=>{const e=document.querySelector('[data-path=\"new_definitions[0].description\"]');e.value='검토자가 고친 설명';e.dispatchEvent(new Event('input',{bubbles:true}));return true;})()")
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-id=path_blocked]').dataset.scopeStatus"), 'PENDING')
        self.assertIn('다시 생성', browser.evaluate("$('seq_eblc_status').textContent"))
        browser.evaluate('flush().then(()=>true)')
        response['stages']['eblc']['stale'] = True
        browser.evaluate("(()=>{api=async function(path,...args){return path.endsWith('/sequence')?"+json.dumps(response)+":scopeBaseApi(path,...args);};document.dispatchEvent(new CustomEvent('studio:moment'));return true;})()")
        browser.wait("$('seq_eblc_status').textContent.includes('다시 생성')")
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-id=path_blocked]').dataset.scopeStatus"), 'PENDING')
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['original_candidate'], candidate)

    def test_three_new_candidates_with_legacy_coc_are_pending_and_explain_format_gap(self):
        from .test_sequence import scene
        legacy=scene(0)['coc'];legacy['evidence_refs']=[self.store.moment(self.ids[0])['frame']['frame_id']]
        candidate={'new_definitions':[definition(condition_id='candidate_'+str(i),condition_class=cls) for i,cls in enumerate(['WORKZONE_OBSTACLE','TRAFFIC_CONTROL','VULNERABLE_ROAD_USER'])],'facts':[],'unresolved_previous_condition_refs':[],'unknowns':[]}
        with self.store.transaction():
            m=self.store.moment(self.ids[0]);self.store.install(m,'sequence_coc',legacy);self.store.save(m,'legacy CoC format fixture')
        self.install_constraints(candidate)
        browser=self.browser_login();browser.wait("document.querySelectorAll('.sequence_condition').length===3")
        browser.evaluate('showStage(2);true')
        self.assertEqual(browser.evaluate("document.querySelector('[data-scope-group=PENDING]').firstChild.textContent"),'적용 상태 계산 전 · 3개')
        self.assertTrue(browser.evaluate("[...document.querySelectorAll('#seq_class_counts li')].every(e=>e.dataset.uncertain==='0')"))
        self.assertEqual(browser.evaluate("[...document.querySelectorAll('#seq_class_counts li')].reduce((n,e)=>n+Number(e.dataset.pending),0)"),3)
        self.assertIn('1단계에서 CoC를 다시 생성',browser.evaluate("document.querySelector('.constraint_format_notice').textContent"))
        self.assertTrue(browser.evaluate("document.querySelector('.constraint_format_notice').checkVisibility()"))
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['original_candidate'],candidate)

    def test_compact_review_excludes_two_candidates_updates_totals_and_preserves_logic(self):
        coc=self.install_coc();coc['entities'].append({'entity_id':'e2','kind':'ZONE','description':'진입 영역','identity_status':'NEW_LOCAL','previous_entity_ref':None,'evidence_refs':coc['evidence_refs']})
        with self.store.transaction():
            m=self.store.moment(self.ids[0]);self.store.install(m,'sequence_coc',{**deepcopy(coc),'original_candidate':deepcopy(coc)});self.store.save(m,'compact constraint fixture')
        defs=[definition(condition_id='workzone',condition_class='WORKZONE_OBSTACLE'),definition(condition_id='pedestrian',condition_class='VULNERABLE_ROAD_USER'),definition(condition_id='traffic',condition_class='TRAFFIC_CONTROL')]
        # Stored verification fields survive removal of the six input menus.
        defs[0].update(preconditions=deepcopy(defs[0]['activation_all_of']),expected_postconditions=deepcopy(defs[0]['release_any_of']),postcondition_window='NEXT_OBSERVATION')
        f=fact();f['evidence_refs']=coc['evidence_refs']
        candidate={'new_definitions':defs,'facts':[f],'unresolved_previous_condition_refs':[],'unknowns':['경로 충돌은 별도 확인 필요']}
        self.install_constraints(candidate)
        browser=self.browser_login();browser.wait("document.querySelectorAll('.sequence_condition').length===3");browser.evaluate('showStage(2);true')
        summaries=browser.evaluate("[...document.querySelectorAll('#seq_candidates summary')].map(e=>e.textContent)")
        for title in ['조건과 행동','조건이 시작되는 때','조건이 끝나는 때','행동 전에 확인할 사실','행동 뒤에 기대하는 사실','기대 결과를 확인할 때']:
            self.assertFalse(any(title in s for s in summaries),title)
        self.assertFalse(browser.evaluate("[...document.querySelectorAll('#seq_candidates [data-path]')].some(e=>/activation_all_of|release_any_of|preconditions|expected_postconditions|postcondition_window/.test(e.dataset.path))"))
        browser.evaluate("document.querySelector('[data-remove=\"new_definitions[2]\"]').click();flush().then(()=>true)")
        browser.evaluate("document.querySelector('[data-remove=\"new_definitions[1]\"]').click();flush().then(()=>true)")
        self.assertEqual(browser.evaluate("document.querySelectorAll('.sequence_condition').length"),1)
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=TRAFFIC_CONTROL]').dataset.count"),'0')
        self.assertEqual(browser.evaluate("document.querySelector('[data-condition-class=VULNERABLE_ROAD_USER]').dataset.count"),'0')
        self.assertIn('이 장면에서 제외 2개',browser.evaluate("$('seq_class_status').textContent"))
        saved=self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']
        self.assertEqual(saved['new_definitions'],[defs[0]])
        self.assertEqual(saved['original_candidate'],candidate)
        self.assertEqual(saved['facts'],candidate['facts'])
        self.assertEqual(saved['unknowns'],candidate['unknowns'])
        browser.evaluate('selectOrdinal(1).then(()=>selectOrdinal(0)).then(()=>true)')
        browser.wait("document.querySelectorAll('.sequence_condition').length===1")
        self.assertIn('현재 제약 1개',browser.evaluate("$('seq_class_status').textContent"))
        self.assertFalse(browser.evaluate("$('seq_accept_constraints').checked"))
