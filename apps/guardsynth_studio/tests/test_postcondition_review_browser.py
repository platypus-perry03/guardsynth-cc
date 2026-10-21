"""B8 skips, waiting, timing edits and missing observations have distinct user paths."""
from copy import deepcopy
import unittest

from . import test_http_browser as http
from . import test_pipeline_scenarios as scenarios
from . import test_studio_properties_browser as properties
from .helpers import edit, approve
from .test_grounded_sequence import moment, definition, guard, fact


class PostconditionReviewBrowserTest(unittest.TestCase):
    setUp = http.HTTPTest.setUp
    tearDown = http.HTTPTest.tearDown
    browser_login = http.HTTPTest.browser_login
    stages = properties.StudioPropertiesBrowserTest.stages
    derive = scenarios.PipelineScenariosTest.derive
    run_button = scenarios.PipelineScenariosTest.run_button
    edit_field = scenarios.PipelineScenariosTest.edit_field

    def prepare(self, action='ENTER', window='UNSPECIFIED', following=False, result='TRUE'):
        d = definition(effect='ALLOW' if action == 'ENTER' else 'FORBID',
                       postcondition_window=window,
                       expected_postconditions=[guard('TRUE' if action == 'ENTER' else 'FALSE',
                                                     predicate='IN', subject='ego', target='e2')])
        ms = [moment(definitions=[d], action=action, target='e2' if action == 'ENTER' else None)]
        if following:
            fs = [fact()]
            if result is not None:
                fs.append(fact(result, predicate='IN', subject='ego', target='e2'))
            ms.append(moment(1, [], fs, previous=True))
        for index, m in enumerate(ms):
            frame = self.store.moment(self.ids[index])['frame']['frame_id']

            def evidence(value):
                if isinstance(value, dict):
                    if 'evidence_refs' in value: value['evidence_refs'] = [frame]
                    for child in value.values(): evidence(child)
                elif isinstance(value, list):
                    for child in value: evidence(child)
            evidence(m)
            for kind, payload in [('sequence_coc', m['coc']), ('sequence_constraints', m['constraints'])]:
                edit(self.service, self.ids[index], kind, payload)
                approve(self.service, self.ids[index], kind)
        self.stages()
        b = self.browser_login(); b.evaluate('showStage(4);true')
        b.wait("!!document.querySelector('#seq_current_result [data-property-id=B8]')")
        return b

    def test_no_performed_entry_has_explanation_and_no_b8_repair_card(self):
        b = self.prepare(action='CONTINUE')
        before = deepcopy(self.store.moment(self.ids[0]))
        text = b.evaluate("document.querySelector('#seq_current_result [data-property-id=B8]').textContent")
        self.assertIn('해당 없음', text)
        self.assertIn('수정할 항목은 없습니다', text)
        self.assertIn('현재 기록 행동: 주행 지속', text)
        self.assertIn('결과를 연결한 행동: 영역 진입', text)
        self.assertFalse(b.evaluate("[...$('seq_current_result').querySelectorAll('.review_item')].some(e=>e.textContent.includes('관련 검사: B8'))"))
        self.assertEqual(self.store.moment(self.ids[0]), before)

    def test_timing_edit_rebuilds_and_next_scene_outcome_passes(self):
        b = self.prepare(following=True)
        b.wait("!!document.querySelector('[data-code=POSTCONDITION_TIMING_REQUIRED] [data-review-suggestion]')")
        b.evaluate("document.querySelector('[data-code=POSTCONDITION_TIMING_REQUIRED] [data-review-suggestion]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"new_definitions[0].postcondition_window\"]')")
        self.edit_field(b, 'new_definitions[0].postcondition_window', 'NEXT_OBSERVATION')
        b.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').click();true")
        b.wait('!state.busy && !!state.moment.approvals.sequence_constraints')
        job = self.derive(b)
        self.assertEqual(next(p for p in job['result']['scenes'][1]['properties']['results'] if p['property_id'] == 'B8')['status'], 'PASS')
        b.wait("!!document.querySelector('[data-postcondition-reason=NEXT_SCENE_PENDING]')")
        text = b.evaluate("document.querySelector('#seq_current_result [data-property-id=B8]').textContent")
        self.assertEqual(b.evaluate("document.querySelector('#seq_current_result [data-property-id=B8]').dataset.propertyStatus"), 'NOT_CHECKED')
        self.assertIn('바로 다음 시점에서 검사', text)
        b.evaluate("[...document.querySelector('[data-postcondition-reason=NEXT_SCENE_PENDING]').querySelectorAll('button')].find(e=>e.textContent==='다음 시점 열기').click();true")
        b.wait('state.moment.ordinal===1 && !state.busy')
        b.evaluate('showStage(4);true')
        b.wait("document.querySelector('#seq_current_result [data-property-id=B8]').dataset.propertyStatus==='PASS'")

    def test_missing_expected_observation_has_input_and_real_recheck(self):
        b = self.prepare(window='NEXT_OBSERVATION', following=True, result=None)
        b.evaluate('loadMoment(state.moments[1].id).then(()=>render()).then(()=>showStage(4));true')
        b.wait("!!document.querySelector('[data-code=POSTCONDITION_UNKNOWN] [data-input-observation=IN]')")
        b.evaluate("document.querySelector('[data-code=POSTCONDITION_UNKNOWN] [data-input-observation=IN]').click();true")
        b.wait("!!document.querySelector('[data-observation-truth]')")
        self.assertEqual(b.evaluate("document.querySelector('[data-observation-truth]').value"), '')
        b.evaluate("(()=>{const t=document.querySelector('[data-observation-truth]');t.value='TRUE';t.dispatchEvent(new Event('change'));const n=document.querySelector('[data-observation-note]');n.value='현재 영상에서 자차가 진입 영역 안에 있는 모습을 확인';n.dispatchEvent(new Event('input'));const f=document.querySelector('[data-observation-evidence]');for(const o of f.options)o.selected=o.value===state.moment.frame.frame_id;f.dispatchEvent(new Event('change'));document.querySelector('[data-save-observation]').click();return true;})()")
        b.wait("!document.querySelector('[data-save-observation]') && !state.busy && !$('seq_revision_status').textContent.includes('저장하고')")
        # Explicit approval and the production CPU stages use the newly saved fact.
        scenarios.PipelineScenariosTest.approve_ui(self, b, 'sequence_constraints')
        job = self.derive(b)
        self.assertEqual(next(p for p in job['result']['scenes'][1]['properties']['results'] if p['property_id'] == 'B8')['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
