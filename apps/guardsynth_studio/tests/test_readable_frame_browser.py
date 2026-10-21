"""Frame identifiers stay in evidence, not in displayed CoC prose."""
from copy import deepcopy
import json
import unittest

from apps.guardsynth_studio.common import uid
from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio.provider import task_instructions
from . import test_http_browser as http
from .test_grounded_sequence import moment


class ReadableFrameBrowserTest(unittest.TestCase):
    setUp = http.HTTPTest.setUp
    tearDown = http.HTTPTest.tearDown
    browser_login = http.HTTPTest.browser_login

    def prepare(self):
        value = moment(1)['coc']
        previous = self.store.moment(self.ids[0])['frame']['frame_id']
        current = self.store.moment(self.ids[1])['frame']['frame_id']
        explanation = f'직전 프레임({previous})과 현재 프레임({current})을 비교하면 자차가 계속 주행했다.'
        value['explanation'] = explanation
        value['observations'] = f'비교 근거: {previous}, {current}'
        value['reason_bindings'] = [{'action_index': 0, 'explanation_excerpt': explanation, 'reasons': []}]
        for entity in value['entities']: entity['evidence_refs'] = [current]
        for action in value['observed_actions']: action['evidence_refs'] = [previous, current]
        value['evidence_refs'] = [previous, current]

        class Provider:
            mode = 'MOCK'; model = 'readable-frame-test'
            def generate(inner, *args):
                return {'parsed_candidate': deepcopy(value), 'raw_output': json.dumps(value),
                        'model_version': inner.model, 'provider_request_id': 'test'}

        self.service.provider = Provider()
        job = self.service.enqueue(self.ids[1], 0, 'SEQ_COC', 'reviewer', uid())
        Worker(self.service).run_once()
        self.assertEqual(self.store.get(job['job_id'], 'job')['status'], 'SUCCEEDED')
        before = deepcopy(self.store.moment(self.ids[1]))
        browser = self.browser_login()
        browser.wait('state.moment?.ordinal===1 && state.navigationPending===null')
        return browser, before, previous, current

    def test_display_and_edit_preserve_evidence_and_original_candidate(self):
        b, before, previous, current = self.prepare()
        expected = '직전 프레임과 현재 프레임을 비교하면 자차가 계속 주행했다.'
        self.assertEqual(b.evaluate("$('seq_explanation').value"), expected)
        self.assertEqual(b.evaluate("$('seq_original_explanation').textContent"), expected)
        self.assertIn('영상 0.000초', b.evaluate("$('seq_observations').textContent"))
        self.assertEqual(self.store.moment(self.ids[1]), before)
        options = b.evaluate("[...document.querySelectorAll('[data-path=\"evidence_refs\"] option')].map(o=>({value:o.value,text:o.textContent}))")
        self.assertTrue(any(o['value'] == previous for o in options))
        self.assertFalse(any(previous in o['text'] or current in o['text'] for o in options))
        b.evaluate("$('seq_explanation').value+=' 영상에서 확인했다.';$('seq_explanation').dispatchEvent(new Event('input'));flush().then(()=>true)")
        b.wait("state.moment.components.sequence_coc.payload.explanation.endsWith('영상에서 확인했다.')")
        stored = self.store.moment(self.ids[1])['components']['sequence_coc']['payload']
        self.assertEqual(stored['reason_bindings'][0]['explanation_excerpt'], expected)
        self.assertEqual(stored['evidence_refs'], [previous, current])
        self.assertEqual(stored['original_candidate'], before['components']['sequence_coc']['payload']['original_candidate'])
        self.assertEqual(stored['raw_output'], before['components']['sequence_coc']['payload']['raw_output'])
        self.assertEqual(b.evaluate("$('error').textContent"), '')
        self.assertEqual(len(self.store.job_ids()), 1)

    def test_readable_display_does_not_make_original_acceptance_a_human_edit(self):
        b, before, _, _ = self.prepare()
        b.evaluate("$('seq_accept_coc').click();flush().then(()=>true)")
        b.wait("!$('seq_approve_coc').disabled")
        b.evaluate("$('seq_approve_coc').click();true")
        b.wait("!state.busy && state.moment.approvals.sequence_coc?.decision==='APPROVE'")
        stored = self.store.moment(self.ids[1])
        self.assertEqual(stored['components']['sequence_coc']['payload']['explanation'], before['components']['sequence_coc']['payload']['explanation'])
        self.assertTrue(stored['components']['sequence_coc']['payload']['accepted_unchanged'])
        self.assertEqual(b.evaluate("$('error').textContent"), '')

    def test_future_generation_instructions_keep_ids_only_in_structured_evidence(self):
        for task in ('SEQ_COC', 'SEQ_CONSTRAINTS'):
            instruction = task_instructions(task)
            self.assertIn('해시·CAN 식별자를 쓰지 않는다', instruction)
            self.assertIn('구조화된 evidence_refs에 그대로 연결', instruction)


if __name__ == '__main__':
    unittest.main()
