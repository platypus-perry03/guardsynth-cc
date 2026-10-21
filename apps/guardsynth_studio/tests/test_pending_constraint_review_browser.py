"""Saved observations can be reviewed and rechecked from verification after reload."""
from copy import deepcopy
import time
import unittest

from apps.guardsynth_studio.jobs import Worker
from . import test_missing_observation_browser as observations
from . import test_pipeline_scenarios as scenarios


class PendingConstraintReviewBrowserTest(unittest.TestCase):
    setUp = observations.MissingObservationBrowserTest.setUp
    tearDown = observations.MissingObservationBrowserTest.tearDown
    browser_login = observations.MissingObservationBrowserTest.browser_login
    start = observations.MissingObservationBrowserTest.start
    approve_ui = observations.MissingObservationBrowserTest.approve_ui
    generate_pair = observations.MissingObservationBrowserTest.generate_pair
    derive = observations.MissingObservationBrowserTest.derive
    run_button = observations.MissingObservationBrowserTest.run_button
    prepare = observations.MissingObservationBrowserTest.prepare
    open_input = observations.MissingObservationBrowserTest.open_input
    save_input = observations.MissingObservationBrowserTest.save_input
    edit_field = scenarios.PipelineScenariosTest.edit_field

    def restore_original(self, b):
        b.evaluate("document.querySelector('[data-input-observation=PASSAGE_COMPLETE]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        self.edit_field(b, 'facts[1].truth', 'TRUE')
        self.approve_ui(b, 'sequence_constraints')
        self.derive(b)
        b.evaluate('showStage(4);true')
        b.wait("!!document.querySelector('#seq_current_result [data-code=LIFECYCLE_CONFLICT]')")
        b.evaluate("document.querySelector('#seq_current_result [data-lifecycle-observation=PASSAGE_COMPLETE]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        self.edit_field(b, 'facts[1].truth', 'UNKNOWN')
        saved = deepcopy(self.store.moment(self.ids[0]))
        self.assertFalse(saved['components']['sequence_constraints']['payload']['accepted_unchanged'])
        self.assertNotIn('sequence_constraints', saved['approvals'])
        self.assertTrue(b.evaluate("$('seq_approve_constraints').disabled"))
        return saved

    def test_restoring_original_can_review_and_recheck_after_reload_without_hidden_checkbox(self):
        from apps.guardsynth_studio.sequence import candidate
        b = self.prepare(existing='UNKNOWN'); saved = self.restore_original(b)
        original = deepcopy(saved['components']['sequence_constraints']['payload']['original_candidate'])
        self.assertEqual(candidate(saved['components']['sequence_constraints']['payload'],'sequence_constraints'),original)
        b.call('Page.reload')
        b.wait("!!state.moment && !$('seq_pending_constraint_review').hidden && !$('seq_approve_constraints_recheck').disabled")
        b.evaluate('showStage(4);true')
        self.assertIn('원문 수용', b.evaluate("$('seq_approve_constraints_recheck').textContent"))
        self.assertIn('판단할 수 없음', b.evaluate("$('seq_pending_constraint_changes').textContent"))
        self.assertFalse(b.evaluate("$('seq_accept_constraints').checked"))
        self.assertEqual(self.store.moment(self.ids[0]),saved)
        # The review shortcut targets the changed passage fact, not an empty definition.
        b.evaluate("$('seq_open_pending_constraints').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        b.evaluate("[...$('seq_review_editor').querySelectorAll('button')].find(e=>e.textContent==='수정창 닫기').click();true")
        result = self.run_pending(b)['result']['scenes'][0]
        self.assertEqual(result['states']['path_blocked']['state'],'ACTIVE')
        self.assertIn('EVIDENCE_MISSING',result['codes'])
        self.assertNotIn('LIFECYCLE_CONFLICT',result['codes'])
        current = self.store.moment(self.ids[0])
        self.assertTrue(current['components']['sequence_constraints']['payload']['accepted_unchanged'])
        self.assertIn('sequence_constraints',current['approvals'])
        self.assertEqual(current['components']['sequence_coc'],saved['components']['sequence_coc'])
        self.assertEqual(current['components']['sequence_constraints']['payload']['original_candidate'],original)
        self.assertEqual(self.service.provider.calls,['SEQ_COC','SEQ_CONSTRAINTS'])

    def test_editor_explicit_original_review_does_not_need_another_acceptance_click(self):
        b = self.prepare(existing='UNKNOWN'); self.restore_original(b)
        b.wait("!!document.querySelector('[data-review-approve=sequence_constraints]') && !document.querySelector('[data-review-approve=sequence_constraints]').disabled")
        self.assertIn('원문 수용',b.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').textContent"))
        self.assertFalse(b.evaluate("$('seq_accept_constraints').checked"))
        b.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').click();true")
        b.wait("!state.busy && !!state.moment.approvals.sequence_constraints")
        result = self.derive(b)['result']['scenes'][0]
        self.assertEqual(result['states']['path_blocked']['state'],'ACTIVE')
        self.assertIn('EVIDENCE_MISSING',result['codes'])
        self.assertEqual(self.service.provider.calls,['SEQ_COC','SEQ_CONSTRAINTS'])

    def run_pending(self, b):
        b.wait("!$('seq_pending_constraint_review').hidden && !$('seq_approve_constraints_recheck').disabled")
        b.evaluate("$('seq_approve_constraints_recheck').click();true")
        b.wait('state.busy')
        end = time.monotonic() + 20
        while time.monotonic() < end:
            Worker(self.service).run_once()
            if not b.evaluate('state.busy'):
                break
            time.sleep(.1)
        b.wait('!state.busy')
        self.assertEqual(b.evaluate("$('error').textContent"), '')
        self.assertEqual(b.evaluate('state.stage'), 4)
        self.assertTrue(b.evaluate("$('seq_pending_constraint_review').hidden"))
        return next(j for j in reversed(self.store.objects('job')) if j['kind'] == 'SEQ_VERIFY')

    def test_reload_recovers_saved_observation_review_and_recheck(self):
        b = self.prepare(); self.open_input(b); self.save_input(b, 'FALSE')
        quality = deepcopy(self.store.objects('sequence_quality'))
        saved = self.store.moment(self.ids[0])
        self.assertNotIn('sequence_constraints', saved['approvals'])
        b.call('Page.reload')
        b.wait("!!state.moment && !$('seq_pending_constraint_review').hidden")
        b.evaluate('showStage(4);true')
        text = b.evaluate("$('seq_pending_constraint_changes').textContent")
        self.assertIn('완전히 지나쳤는지', text)
        self.assertIn('아직 완전히 지나치지 않았음', text)
        self.assertIn('공사 구역 옆을 지나가는 중', text)
        self.assertTrue(b.evaluate("$('seq_check').disabled && $('seq_pending_constraint_review').checkVisibility()"))
        result = self.run_pending(b)['result']['scenes'][0]
        self.assertNotIn('EVIDENCE_MISSING', result['codes'])
        self.assertEqual(result['states']['path_blocked']['state'], 'ACTIVE')
        self.assertEqual(result['states']['path_blocked']['release_guard'], 'FALSE')
        m = self.store.moment(self.ids[0])
        self.assertEqual(m['approvals']['sequence_constraints']['component_id'], m['components']['sequence_constraints']['id'])
        self.assertEqual(m['components']['sequence_coc'], saved['components']['sequence_coc'])
        self.assertEqual(m['components']['sequence_constraints']['payload'], saved['components']['sequence_constraints']['payload'])
        self.assertEqual(self.store.objects('sequence_quality'), quality)
        self.assertEqual(self.service.provider.calls, ['SEQ_COC', 'SEQ_CONSTRAINTS'])

    def test_unknown_review_runs_but_keeps_the_unresolved_result(self):
        b = self.prepare(); self.open_input(b); self.save_input(b, 'UNKNOWN')
        self.assertIn('판단할 수 없음', b.evaluate("$('seq_pending_constraint_changes').textContent"))
        result = self.run_pending(b)['result']['scenes'][0]
        self.assertIn('EVIDENCE_MISSING', result['codes'])
        self.assertEqual(result['states']['path_blocked']['state'], 'ACTIVE')
        self.assertIn('확인 필요', b.evaluate("$('seq_current_result').textContent"))

    def test_coc_review_is_required_before_constraint_approval(self):
        b = self.prepare(); self.open_input(b); self.save_input(b, 'FALSE')
        b.evaluate("$('seq_explanation').value='주행 설명 수정';$('seq_explanation').dispatchEvent(new Event('input',{bubbles:true}));flush().then(()=>true)")
        b.wait("$('seq_verify_guidance').textContent.includes('CoC 검토')")
        self.assertTrue(b.evaluate("$('seq_pending_constraint_review').hidden"))
        self.assertNotIn('sequence_coc', self.store.moment(self.ids[0])['approvals'])
        self.assertNotIn('sequence_constraints', self.store.moment(self.ids[0])['approvals'])

    def test_pending_review_can_reopen_saved_fact_without_regeneration(self):
        b = self.prepare(); self.open_input(b); self.save_input(b, 'FALSE')
        before = deepcopy(self.store.moment(self.ids[0]))
        b.evaluate("[...$('seq_review_editor').querySelectorAll('button')].find(x=>x.textContent==='수정창 닫기').click();$('seq_open_pending_constraints').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        self.assertEqual(b.evaluate("document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]').value"), 'FALSE')
        self.assertEqual(self.store.moment(self.ids[0]), before)
        self.assertEqual(self.service.provider.calls, ['SEQ_COC', 'SEQ_CONSTRAINTS'])

    def test_empty_constraint_edit_opens_a_reviewable_collection(self):
        b = self.prepare()
        b.evaluate("queue('sequence_constraints',{new_definitions:[],facts:[],unresolved_previous_condition_refs:[],unknowns:[],accepted_unchanged:false}).then(()=>flush()).then(()=>{document.dispatchEvent(new CustomEvent('studio:moment'));return true;})")
        b.wait("!$('seq_pending_constraint_review').hidden")
        b.evaluate("$('seq_open_pending_constraints').click();true")
        b.wait("!$('seq_review_editor').hidden && !$('seq_approve_constraints_recheck').disabled")
        self.assertIn('현재 입력에 제약 정의가 없습니다', b.evaluate("$('seq_review_editor').textContent"))
        self.assertNotIn('이 항목은 현재 입력에서 삭제되었거나', b.evaluate("$('seq_review_editor').textContent"))
        self.assertFalse(b.evaluate("!!document.querySelector('#seq_review_editor [data-review-approve]')"))
        self.run_pending(b)
        self.assertEqual(self.service.provider.calls, ['SEQ_COC', 'SEQ_CONSTRAINTS'])


if __name__ == '__main__':
    unittest.main()
