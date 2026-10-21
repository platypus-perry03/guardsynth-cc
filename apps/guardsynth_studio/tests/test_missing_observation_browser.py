"""A missing lifecycle observation has an actual save and recheck path."""
from copy import deepcopy
import json
import unittest

from . import test_http_browser as http
from . import test_pipeline_scenarios as scenarios
from .test_grounded_sequence import guard, fact


class MissingObservationBrowserTest(unittest.TestCase):
    setUp = http.HTTPTest.setUp
    tearDown = http.HTTPTest.tearDown
    browser_login = http.HTTPTest.browser_login
    start = scenarios.PipelineScenariosTest.start
    approve_ui = scenarios.PipelineScenariosTest.approve_ui
    generate_pair = scenarios.PipelineScenariosTest.generate_pair
    derive = scenarios.PipelineScenariosTest.derive
    run_button = scenarios.PipelineScenariosTest.run_button

    def prepare(self, existing=None, missing_start=False, repeated_guard=False):
        b = self.start(action='CONTINUE')
        generate = self.service.provider.generate

        def output(kind, *args):
            result = generate(kind, *args)
            candidate = result['parsed_candidate']
            if kind == 'SEQ_COC':
                candidate['entities'][2]['description'] = '바리케이드로 구분된 공사 구역'
            if kind == 'SEQ_CONSTRAINTS':
                d = candidate['new_definitions'][0]
                d.update(description='우측 공사 구역은 자차 진입 금지 후보로 본다.',
                         condition_class='WORKZONE_OBSTACLE',
                         activation_all_of=[guard(predicate='ZONE_CLOSED', subject='e2', target=None)],
                         release_any_of=[guard(predicate='PASSAGE_COMPLETE', subject='ego', target='e2')])
                frame = self.store.moment(self.ids[0])['frame']['frame_id']
                candidate['facts'] = [fact(predicate='ZONE_CLOSED', subject='e2', target=None)]
                if missing_start:candidate['facts']=[]
                if repeated_guard:d['release_any_of'].append(deepcopy(d['release_any_of'][0]))
                if existing is not None:
                    candidate['facts'].append(fact(existing, predicate='PASSAGE_COMPLETE', subject='ego', target='e2'))
                for f in candidate['facts']:
                    f['evidence_refs'] = [frame]
            result['raw_output'] = json.dumps(candidate)
            return result

        self.service.provider.generate = output
        self.generate_pair(b)
        self.derive(b)
        b.evaluate('showStage(4);true')
        b.wait("!!document.querySelector('[data-input-observation=PASSAGE_COMPLETE]')")
        return b

    def test_two_missing_observations_show_named_buttons_and_related_constraint(self):
        b=self.prepare(missing_start=True)
        before=deepcopy(self.store.moment(self.ids[0]))
        selector="#seq_current_result [data-code=EVIDENCE_MISSING] .review_compact_actions"
        labels=b.evaluate("[...document.querySelector("+json.dumps(selector)+").querySelectorAll('button')].map(e=>e.textContent)")
        self.assertIn('통행 차단 여부 입력',labels)
        self.assertIn('통과 여부 입력',labels)
        self.assertNotIn('관찰 입력',labels)
        for button,phase,question in [('통행 차단 여부 입력','조건 시작','통행이 막혀 있는지'),('통과 여부 입력','조건 해제','완전히 지나쳤는지')]:
            b.evaluate("[...document.querySelector("+json.dumps(selector)+").querySelectorAll('button')].find(e=>e.textContent==="+json.dumps(button)+").click();true")
            b.wait("!!document.querySelector('#seq_review_editor [data-observation-context]')")
            text=b.evaluate("$('seq_review_editor').textContent")
            self.assertIn('우측 공사 구역은 자차 진입 금지 후보로 본다.',text)
            self.assertIn(phase,text);self.assertIn(question,text)
            self.assertTrue(b.evaluate("(()=>{const r=document.querySelector('#seq_review_editor [data-observation-context] blockquote').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;})()"))
            self.assertEqual(b.evaluate("document.querySelector('[data-observation-truth]').value"),'')
            b.evaluate("[...$('seq_review_editor').querySelectorAll('button')].find(e=>e.textContent==='수정창 닫기').click();true")
        self.assertEqual(self.store.moment(self.ids[0]),before)

    def test_repeated_guard_has_one_compact_observation_action(self):
        b=self.prepare(repeated_guard=True)
        labels=b.evaluate("[...document.querySelector('#seq_current_result [data-code=EVIDENCE_MISSING] .review_compact_actions').querySelectorAll('button')].map(e=>e.textContent)")
        self.assertEqual(labels.count('통과 여부 입력'),1)

    def test_existing_unknown_compact_editor_keeps_definition_context(self):
        b=self.prepare(existing='UNKNOWN')
        before=deepcopy(self.store.moment(self.ids[0]))
        b.evaluate("document.querySelector('#seq_current_result [data-code=EVIDENCE_MISSING] .review_compact_actions [data-batch-source=sequence_constraints]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-observation-context]') && !!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        text=b.evaluate("$('seq_review_editor').textContent")
        self.assertIn('우측 공사 구역은 자차 진입 금지 후보로 본다.',text)
        self.assertIn('조건 해제',text);self.assertIn('완전히 지나쳤는지',text)
        self.assertTrue(b.evaluate("(()=>{const r=document.querySelector('#seq_review_editor [data-observation-context] blockquote').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;})()"))
        self.assertEqual(self.store.moment(self.ids[0]),before)

    def open_input(self, b):
        b.evaluate("document.querySelector('[data-input-observation=PASSAGE_COMPLETE]').click();true")
        b.wait("!!document.querySelector('[data-observation-truth]')")

    def save_input(self, b, truth):
        b.evaluate("(()=>{const t=document.querySelector('[data-observation-truth]');t.value=" + json.dumps(truth) + ";t.dispatchEvent(new Event('change'));const n=document.querySelector('[data-observation-note]');n.value='현재 영상에서 공사 구역 옆을 지나가는 중임을 확인';n.dispatchEvent(new Event('input'));const f=document.querySelector('[data-observation-evidence]');for(const o of f.options)o.selected=o.value===state.moment.frame.frame_id;f.dispatchEvent(new Event('change'));document.querySelector('[data-save-observation]').click();return true;})()")
        b.wait("!document.querySelector('[data-save-observation]') && !state.busy && !$('seq_resume').hidden")
        b.wait("!$('seq_revision_status').textContent.includes('저장하고')")
        self.assertEqual(b.evaluate("$('error').textContent"), '')

    def test_missing_fact_table_and_cancel_do_not_change_input(self):
        b = self.prepare()
        before = deepcopy(self.store.moment(self.ids[0]))
        text = b.evaluate("document.querySelector('[data-lifecycle-evidence]').textContent")
        self.assertIn('통행이 막혀 있는지', text)
        self.assertIn('완전히 지나쳤는지', text)
        self.assertIn('관찰 사실이 없음', text)
        self.assertIn('행동 수정 불필요', text)
        self.open_input(b)
        self.assertEqual(b.evaluate("document.querySelector('[data-observation-truth]').value"), '')
        self.assertTrue(b.evaluate("document.querySelector('[data-observation-evidence]').options[0].textContent.startsWith('현재 영상')"))
        b.evaluate("[...$('seq_review_editor').querySelectorAll('button')].find(x=>x.textContent==='수정창 닫기').click();true")
        self.assertEqual(self.store.moment(self.ids[0]), before)

    def test_not_passed_fact_is_saved_compiled_and_clears_missing_release(self):
        b = self.prepare()
        before = deepcopy(self.store.moment(self.ids[0]))
        quality = deepcopy(self.store.objects('sequence_quality'))
        self.open_input(b)
        # No observation is assumed, and a definite answer needs evidence.
        b.evaluate("document.querySelector('[data-save-observation]').click();true")
        self.assertIn('확인 상태와 근거 설명', b.evaluate("$('seq_review_editor').textContent"))
        self.assertEqual(self.store.moment(self.ids[0]), before)
        self.save_input(b, 'FALSE')
        current = self.store.moment(self.ids[0])
        original = before['components']['sequence_constraints']['payload']
        saved = current['components']['sequence_constraints']['payload']
        self.assertEqual(saved['new_definitions'], original['new_definitions'])
        self.assertEqual(saved['original_candidate'], original['original_candidate'])
        self.assertEqual(current['components']['sequence_coc'], before['components']['sequence_coc'])
        self.assertEqual(saved['facts'][-1]['atom']['predicate'], 'PASSAGE_COMPLETE')
        self.assertEqual(saved['facts'][-1]['truth'], 'FALSE')
        self.approve_ui(b, 'sequence_constraints')
        checked = self.derive(b)['result']['scenes'][0]
        self.assertEqual(checked['states']['path_blocked']['release_guard'], 'FALSE')
        self.assertEqual(checked['states']['path_blocked']['state'], 'ACTIVE')
        self.assertNotIn('EVIDENCE_MISSING', checked['codes'])
        self.assertEqual(self.store.objects('sequence_quality'), quality)
        self.assertEqual(self.service.provider.calls, ['SEQ_COC', 'SEQ_CONSTRAINTS'])

    def test_unknown_is_saved_without_claiming_release(self):
        b = self.prepare(); self.open_input(b); self.save_input(b, 'UNKNOWN')
        self.approve_ui(b, 'sequence_constraints')
        checked = self.derive(b)['result']['scenes'][0]
        self.assertEqual(checked['states']['path_blocked']['release_guard'], 'UNKNOWN')
        self.assertEqual(checked['states']['path_blocked']['state'], 'ACTIVE')
        self.assertIn('EVIDENCE_MISSING', checked['codes'])

    def test_confirmed_passage_exposes_conflicting_definition_instead_of_forcing_pass(self):
        b = self.prepare(); self.open_input(b); self.save_input(b, 'TRUE')
        self.approve_ui(b, 'sequence_constraints')
        checked = self.derive(b)['result']['scenes'][0]
        self.assertIn('LIFECYCLE_CONFLICT', checked['codes'])
        self.assertEqual(checked['status'], 'CONTRADICTION')

    def test_existing_unknown_opens_existing_fact_without_duplicate(self):
        b = self.prepare(existing='UNKNOWN')
        b.evaluate("document.querySelector('[data-input-observation=PASSAGE_COMPLETE]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        self.assertFalse(b.evaluate("!!document.querySelector('[data-save-observation]')"))
        self.assertIn('우측 공사 구역은 자차 진입 금지 후보로 본다.',b.evaluate("$('seq_review_editor').textContent"))
        self.assertIn('조건 해제',b.evaluate("$('seq_review_editor').textContent"))
        self.assertEqual(len(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['facts']), 2)


if __name__ == '__main__':
    unittest.main()
