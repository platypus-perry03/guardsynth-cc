"""Browser relation signature controls and stale entity binding prevention."""
from copy import deepcopy
import json
import unittest

from . import test_http_browser as http_browser
from . import test_grounded_browser as grounded_browser
from .helpers import edit, approve


class RelationGrammarBrowserTest(unittest.TestCase):
    setUp=http_browser.HTTPTest.setUp
    tearDown=http_browser.HTTPTest.tearDown
    browser_login=http_browser.HTTPTest.browser_login
    coc_candidate=grounded_browser.GroundedBrowserTest.coc_candidate

    def test_inherited_offscreen_area_is_editable_without_current_entity(self):
        from .test_grounded_sequence import moment,fact
        original=moment()
        fid=self.store.moment(self.ids[0])['frame']['frame_id']
        for e in original['coc']['entities']:e['evidence_refs']=[fid]
        original['coc']['evidence_refs']=[fid]
        original['coc']['observed_actions'][0]['evidence_refs']=[fid]
        original['constraints']['facts'][0]['evidence_refs']=[fid]
        original['coc']['entities'][2]['description']='이전 장면의 공사 구역'
        edit(self.service,self.ids[0],'sequence_coc',original['coc']);approve(self.service,self.ids[0],'sequence_coc')
        edit(self.service,self.ids[0],'sequence_constraints',original['constraints']);approve(self.service,self.ids[0],'sequence_constraints')
        current=moment(2,[],[fact('UNKNOWN',predicate='PASSAGE_COMPLETE',subject='ego',target='e2')])
        fid=self.store.moment(self.ids[2])['frame']['frame_id']
        current['coc']['entities']=current['coc']['entities'][:1]
        current['coc']['entities'][0]['evidence_refs']=[fid]
        current['coc']['evidence_refs']=[fid]
        current['coc']['observed_actions'][0]['evidence_refs']=[fid]
        current['constraints']['facts'][0]['evidence_refs']=[fid]
        edit(self.service,self.ids[2],'sequence_coc',current['coc']);approve(self.service,self.ids[2],'sequence_coc')
        edit(self.service,self.ids[2],'sequence_constraints',current['constraints'])
        before=deepcopy(self.store.moment(self.ids[2]))
        b=self.browser_login();b.evaluate('loadMoment('+json.dumps(self.ids[2])+').then(()=>true)')
        b.wait('state.moment?.ordinal===2 && state.navigationPending===null');b.evaluate('showStage(2);true')
        b.wait("!!document.querySelector('[data-path=\"facts[0].atom.object_ref\"]')")
        choices=b.evaluate("[...document.querySelector('[data-path=\"facts[0].atom.object_ref\"]').options].filter(o=>!o.disabled&&o.value).map(o=>({id:o.value,label:o.textContent}))")
        self.assertIn({'id':'e2','label':'이전 장면의 공사 구역'},choices)
        self.assertFalse(b.evaluate("$('seq_approve_constraints').disabled"))
        self.assertEqual(self.store.moment(self.ids[2]),before)
        self.assertEqual([e['entity_id'] for e in before['components']['sequence_coc']['payload']['entities']],['ego'])

    def install(self, invalid=False):
        coc=self.coc_candidate();fid=coc['evidence_refs'][0]
        coc['entities'].extend([{'entity_id':eid,'kind':kind,'description':desc,'identity_status':'NEW_LOCAL','previous_entity_ref':None,'evidence_refs':[fid]}
                               for eid,kind,desc in [('e2','LANE','현재 주행 차로'),('e3','ZONE','우측 공사 구역'),('e4','OBSTACLE','굴착기')]])
        edit(self.service,self.ids[0],'sequence_coc',coc);approve(self.service,self.ids[0],'sequence_coc')
        bundle={'new_definitions':[],'facts':[{'atom':{'predicate':'ZONE_CLOSED','subject_ref':'e3','object_ref':'ego' if invalid else None},'truth':'TRUE','evidence_refs':[fid],'evidence_note':'공사 구역의 통행 제한 여부'}],'unresolved_previous_condition_refs':[],'unknowns':[]}
        edit(self.service,self.ids[0],'sequence_constraints',bundle)
        return coc,bundle

    def test_unary_hides_comparison_and_predicates_are_grouped(self):
        self.install();b=self.browser_login();b.evaluate('showStage(2);true')
        b.wait("!!document.querySelector('[data-path=\"facts[0].atom.predicate\"] optgroup')")
        self.assertEqual(b.evaluate("document.querySelector('[data-path=\"facts[0].atom.predicate\"]').querySelectorAll('optgroup').length"),6)
        self.assertFalse(b.evaluate("!!document.querySelector('[data-path=\"facts[0].atom.object_ref\"]')"))
        self.assertEqual(set(b.evaluate("[...document.querySelector('[data-path=\"facts[0].atom.subject_ref\"]').options].filter(o=>!o.disabled).map(o=>o.value)")),{'e2','e3'})

    def test_containment_only_offers_areas_and_does_not_change_truth(self):
        self.install();b=self.browser_login();b.evaluate('showStage(2);true')
        b.wait("!!document.querySelector('[data-path=\"facts[0].atom.predicate\"] optgroup')")
        b.evaluate("(()=>{const e=document.querySelector('[data-path=\"facts[0].atom.predicate\"]');e.value='IN';e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()")
        b.wait("!!document.querySelector('[data-path=\"facts[0].atom.object_ref\"]')")
        targets=b.evaluate("[...document.querySelector('[data-path=\"facts[0].atom.object_ref\"]').options].filter(o=>o.value&&!o.disabled).map(o=>o.value)")
        self.assertEqual(set(targets),{'e2','e3'})
        b.evaluate("flush().then(()=>true)")
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['facts'][0]['truth'],'TRUE')
        self.assertTrue(b.evaluate("$('seq_approve_constraints').disabled"))

    def test_existing_invalid_unary_requires_explicit_clear(self):
        self.install(invalid=True);before=deepcopy(self.store.moment(self.ids[0]));b=self.browser_login();b.evaluate('showStage(2);true')
        b.wait("[...document.querySelectorAll('#seq_candidates button')].some(e=>e.textContent==='불필요한 비교 대상 연결 제거')")
        self.assertEqual(self.store.moment(self.ids[0]),before)
        self.assertTrue(b.evaluate("$('seq_approve_constraints').disabled"))
        b.evaluate("[...document.querySelectorAll('#seq_candidates button')].find(e=>e.textContent==='불필요한 비교 대상 연결 제거').click();true")
        b.evaluate("flush().then(()=>true)")
        b.wait("!$('seq_approve_constraints').disabled")
        atom=self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['facts'][0]
        self.assertIsNone(atom['atom']['object_ref']);self.assertEqual(atom['truth'],'TRUE')

    def test_entity_reuse_has_one_notice_and_blocks_approval_and_eblc(self):
        coc,bundle=self.install();approve(self.service,self.ids[0],'sequence_constraints')
        coc['entities'][2]['description']='새로 해석한 다른 주행 차로'
        # Change a referenced region as well; equal kinds must not bypass binding.
        coc['entities'][3]['description']='이전과 다른 공사 구역'
        edit(self.service,self.ids[0],'sequence_coc',coc);approve(self.service,self.ids[0],'sequence_coc')
        edit(self.service,self.ids[0],'sequence_constraints',bundle)
        b=self.browser_login();b.evaluate('showStage(2);true');b.wait("!!document.querySelector('[data-binding-gap]')")
        self.assertEqual(b.evaluate("document.querySelectorAll('[data-binding-gap]').length"),1)
        self.assertTrue(b.evaluate("$('seq_approve_constraints').disabled && $('seq_generate_eblc').disabled"))
        self.assertIn('다시 생성',b.evaluate("$('seq_constraints_status').textContent"))
        self.assertEqual(self.store.objects('job'),[])
