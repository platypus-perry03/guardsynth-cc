"""Original quality explains its findings; current checks have explicit state."""
from copy import deepcopy
import json
import unittest

from apps.guardsynth_studio import sequence
from apps.guardsynth_studio.common import uid
from apps.guardsynth_studio.jobs import Worker
from . import test_http_browser as http
from . import test_pipeline_scenarios as scenarios
from .test_grounded_sequence import guard


class VerificationGuidanceBrowserTest(unittest.TestCase):
    setUp = http.HTTPTest.setUp
    tearDown = http.HTTPTest.tearDown
    browser_login = http.HTTPTest.browser_login
    start = scenarios.PipelineScenariosTest.start
    approve_ui = scenarios.PipelineScenariosTest.approve_ui
    generate_pair = scenarios.PipelineScenariosTest.generate_pair
    derive = scenarios.PipelineScenariosTest.derive
    run_button = scenarios.PipelineScenariosTest.run_button
    edit_field = scenarios.PipelineScenariosTest.edit_field

    def prepare(self):
        b = self.start()
        generate = self.service.provider.generate

        def output(kind, *args):
            result = generate(kind, *args)
            if kind == 'SEQ_CONSTRAINTS':
                result['parsed_candidate']['new_definitions'][0]['release_any_of'] = [guard(predicate='PASSAGE_COMPLETE', subject='ego', target='e2')]
                result['raw_output'] = json.dumps(result['parsed_candidate'])
            return result

        self.service.provider.generate = output
        self.generate_pair(b)
        b.evaluate("showStage(4);document.querySelector('.review_quality').open=true;true")
        b.wait("!!document.querySelector('[data-original-quality]')")
        return b

    def test_original_review_count_names_scene_and_shows_missing_release(self):
        b = self.prepare()
        record = deepcopy(self.store.objects('sequence_quality'))
        self.assertIn('평가한 시점 1개', b.evaluate("$('seq_quality').textContent"))
        self.assertIn('오류 개수가 아니라', b.evaluate("$('seq_quality').textContent"))
        text = b.evaluate("document.querySelector('[data-first-review=EVIDENCE_MISSING]').textContent")
        self.assertIn('보행자가 진입 경로를 점유함', text)
        self.assertIn('완전히 지나쳤는지', text)
        self.assertIn('해제 조건을 확인할 관찰', text)
        self.assertEqual(b.evaluate("document.querySelector('[data-original-quality]').querySelectorAll('input,textarea,select,button').length"), 0)
        self.assertEqual(self.store.objects('sequence_quality'), record)

    def test_current_eblc_enables_verification_despite_original_review_required(self):
        b = self.prepare(); self.run_button(b, 'seq_generate_eblc')
        b.evaluate('showStage(4);true')
        self.assertFalse(b.evaluate("$('seq_check').disabled"))
        self.assertIn('최신 EBLC가 준비', b.evaluate("$('seq_verify_guidance').textContent"))
        self.assertEqual(b.evaluate("$('seq_check').textContent"), '검증 실행')
        self.run_button(b, 'seq_check')
        self.assertEqual(self.store.objects('job')[-1]['result']['scenes'][0]['status'], 'REVIEW_REQUIRED')

    def test_finished_review_required_check_explains_disabled_button_and_rearm(self):
        b = self.prepare(); self.derive(b)
        b.evaluate('showStage(4);true')
        self.assertTrue(b.evaluate("$('seq_check').disabled && !$('seq_reset_verify').disabled"))
        self.assertEqual(b.evaluate("$('seq_check').textContent"), '검증 완료')
        self.assertIn('현재 입력의 검증이 완료', b.evaluate("$('seq_verify_guidance').textContent"))
        self.assertIn('해제', b.evaluate("$('seq_current_result').textContent"))
        b.evaluate("$('seq_reset_verify').click();true")
        self.assertFalse(b.evaluate("$('seq_check').disabled"))
        self.run_button(b, 'seq_check')

    def test_original_findings_do_not_change_after_edit_and_current_rebuild(self):
        b = self.prepare(); self.derive(b)
        before = deepcopy(self.store.objects('sequence_quality'))
        b.evaluate('showStage(2);true')
        self.edit_field(b, 'new_definitions[0].description', '현재 수정한 제약 설명')
        self.approve_ui(b, 'sequence_constraints'); self.run_button(b, 'seq_generate_eblc')
        b.evaluate("showStage(4);document.querySelector('.review_quality').open=true;true")
        self.assertFalse(b.evaluate("$('seq_check').disabled"))
        self.assertIn('보행자가 진입 경로를 점유함', b.evaluate("document.querySelector('[data-original-quality]').textContent"))
        self.assertNotIn('현재 수정한 제약 설명', b.evaluate("document.querySelector('[data-original-quality]').textContent"))
        self.assertEqual(self.store.objects('sequence_quality'), before)

    def test_reload_resumes_queued_verification_without_enqueuing_another(self):
        b = self.prepare(); self.run_button(b, 'seq_generate_eblc')
        queued = sequence.enqueue_stage(self.service, self.extraction, 'SEQ_VERIFY', 'reviewer', uid())
        before = len(self.store.objects('job'))
        b.call('Page.reload')
        b.wait("!!state.moment && $('seq_check').textContent==='검증 중…'")
        self.assertTrue(b.evaluate("state.busy && $('seq_check').disabled"))
        self.assertIn('진행 중', b.evaluate("$('seq_verify_guidance').textContent"))
        Worker(self.service).run_once()
        b.wait("!state.busy && $('seq_check').textContent==='검증 완료'")
        self.assertEqual(len(self.store.objects('job')), before)
        self.assertEqual(self.store.get(queued['job_id'], 'job')['status'], 'SUCCEEDED')
        self.assertEqual(self.service.provider.calls, ['SEQ_COC', 'SEQ_CONSTRAINTS'])
