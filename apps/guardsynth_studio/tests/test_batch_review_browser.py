"""Collect verification corrections explicitly, then save and verify once."""
from copy import deepcopy
import json
import threading
import unittest

from apps.guardsynth_studio import sequence
from apps.guardsynth_studio.jobs import Worker
from . import test_lifecycle_correction_browser as lifecycle
from .helpers import edit, approve
from . import test_missing_observation_browser as observations


class BatchReviewBrowserTest(unittest.TestCase):
    setUp = lifecycle.LifecycleCorrectionBrowserTest.setUp
    tearDown = lifecycle.LifecycleCorrectionBrowserTest.tearDown
    browser_login = lifecycle.LifecycleCorrectionBrowserTest.browser_login
    stages = lifecycle.LifecycleCorrectionBrowserTest.stages
    start = observations.MissingObservationBrowserTest.start
    approve_ui = observations.MissingObservationBrowserTest.approve_ui
    generate_pair = observations.MissingObservationBrowserTest.generate_pair
    derive = observations.MissingObservationBrowserTest.derive
    run_button = observations.MissingObservationBrowserTest.run_button
    prepare = lifecycle.LifecycleCorrectionBrowserTest.prepare

    def open_compact(self, b, component, location='관찰 사실 2'):
        b.evaluate("(()=>{const e=[...document.querySelectorAll('.review_compact_actions [data-batch-source]')].find(e=>e.dataset.batchSource===" + json.dumps(component) + " && e.textContent.includes(" + json.dumps(location) + "));if(!e)throw Error('Missing compact editor');e.click();return true;})()")
        ready = "$('seq_review_editor').checkVisibility() && $('seq_review_editor').dataset.component===" + json.dumps(component)
        if location != '수정 입력':
            ready += " && $('seq_review_editor').querySelector('h3').textContent.includes(" + json.dumps(location) + ")"
        b.wait(ready)

    def change(self, b, path, value):
        b.evaluate("(()=>{const e=[...$('seq_review_editor').querySelectorAll('[data-path]')].find(e=>e.dataset.path===" + json.dumps(path) + ");if(!e)throw Error('Missing field');e.value=" + json.dumps(value) + ";e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input'));return true;})()")
        b.wait("!$('seq_batch_review').hidden")

    def test_real_format_error_points_to_editable_item(self):
        b=self.prepare()
        before=deepcopy(self.store.moment(self.ids[1]))
        self.open_compact(b,'sequence_constraints')
        self.change(b,'facts[1].truth','FALSE')
        b.evaluate("document.querySelector('#seq_review_editor [data-path=\"facts[1].atom.object_ref\"]').append(new Option('잘못 연결된 차량','e1'));true")
        self.change(b,'facts[1].atom.object_ref','e1')
        self.assertTrue(b.evaluate("$('seq_apply_verify').disabled"))
        self.assertIn('종류와 확인할 관계가 맞지',b.evaluate("$('seq_batch_changes').textContent"))
        b.evaluate("document.querySelector('[data-batch-format=\"sequence_constraints/facts/1\"]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].atom.object_ref\"]') && $('seq_review_editor').querySelector('details').open")
        self.change(b,'facts[1].atom.object_ref','e2')
        self.assertFalse(b.evaluate("$('seq_apply_verify').disabled"))
        self.assertEqual(self.store.moment(self.ids[1]),before)

    def run_review(self, b, button):
        stopped = threading.Event()
        def worker():
            while not stopped.is_set():
                Worker(self.service).run_once(); stopped.wait(.02)
        runner = threading.Thread(target=worker, daemon=True); runner.start()
        try:
            b.wait("!$('" + button + "').disabled")
            b.evaluate("$('" + button + "').click();true")
            b.wait("!state.busy && $('seq_batch_review').hidden")
            self.assertEqual(b.evaluate("$('error').textContent"), '')
        finally:
            stopped.set(); runner.join(timeout=10)
        return sequence.latest_stage(self.service, self.extraction, 'SEQ_VERIFY')

    def test_multiple_component_edits_are_not_saved_until_apply_and_rechecked_once(self):
        b = self.prepare(duplicate=True)
        before = deepcopy(self.store.moment(self.ids[1])); origin = deepcopy(self.store.moment(self.ids[0]))
        jobs = len(self.store.objects('job'))
        self.open_compact(b, 'sequence_constraints')
        self.change(b, 'facts[1].truth', 'FALSE')
        self.change(b, 'facts[1].evidence_note', '현재 영상에서 아직 공사 구역 옆을 지나가는 중이다.')
        self.open_compact(b, 'sequence_coc', '대상 관계 1')
        self.change(b, 'relations[0].truth', 'UNKNOWN')
        self.assertEqual(self.store.moment(self.ids[1]), before)
        self.assertEqual(len(self.store.objects('job')), jobs)
        self.assertIn('모아 둔 수정', b.evaluate("$('seq_batch_review').textContent"))
        self.assertTrue(b.evaluate("$('seq_check').disabled"))
        self.run_review(b, 'seq_apply_review')
        saved = self.store.moment(self.ids[1])
        self.assertEqual(len(self.store.objects('job')), jobs)
        self.assertEqual(saved['components']['sequence_constraints']['payload']['facts'][1]['truth'], 'FALSE')
        self.assertEqual(saved['components']['sequence_coc']['payload']['relations'][0]['truth'], 'UNKNOWN')
        for kind in ('sequence_coc', 'sequence_constraints'):
            self.assertEqual(saved['approvals'][kind]['component_id'], saved['components'][kind]['id'])
        b.wait("!$('seq_recheck_saved').hidden")
        verified = self.run_review(b, 'seq_recheck_saved')
        row = verified['result']['scenes'][1]
        self.assertEqual(row['states']['path_blocked']['state'], 'ACTIVE')
        self.assertNotIn('LIFECYCLE_CONFLICT', row['codes'])
        self.assertEqual(verified['inputs']['snapshot']['moments'][1]['revision'], saved['revision'])
        self.assertEqual(self.store.moment(self.ids[0]), origin)
        self.assertEqual(b.evaluate('state.moment.ordinal'), 1)
        self.assertEqual(len([j for j in self.store.objects('job')[jobs:] if j['kind']=='SEQ_VERIFY']), 1)

    def test_reload_navigation_and_cancel_preserve_unapplied_drafts(self):
        b = self.prepare(); before = deepcopy(self.store.moment(self.ids[1]))
        self.open_compact(b, 'sequence_constraints')
        self.change(b, 'facts[1].truth', 'FALSE')
        self.change(b, 'facts[1].evidence_note', '아직 오른쪽에 공사 구역이 보인다.')
        b.call('Page.reload')
        b.wait("state.moment?.ordinal===1 && !$('seq_batch_review').hidden && !$('seq_apply_review').disabled")
        self.assertIn('아직 오른쪽에 공사 구역', b.evaluate("$('seq_batch_changes').textContent"))
        b.evaluate('loadMoment(state.moments[0].id).then(()=>loadMoment(state.moments[1].id)).then(()=>true)')
        b.wait("state.moment?.ordinal===1 && !$('seq_batch_review').hidden && !$('seq_apply_review').disabled")
        self.assertEqual(self.store.moment(self.ids[1]), before)
        b.evaluate("$('seq_discard_review').click();true")
        b.wait("$('seq_batch_review').hidden && !$('seq_batch_feedback').textContent.includes('완료')")
        self.assertEqual(self.store.moment(self.ids[1]), before)
        b.call('Page.reload')
        b.wait("state.moment?.ordinal===1 && !!document.querySelector('.compact_review')")
        self.assertTrue(b.evaluate("$('seq_batch_review').hidden"))

    def test_unknown_is_pending_not_an_error_and_keep_does_not_write_or_rerun(self):
        b = self.prepare(uncertainty=True)
        self.open_compact(b, 'sequence_constraints')
        self.change(b, 'facts[1].truth', 'UNKNOWN')
        checked = self.run_review(b, 'seq_apply_verify')
        row = checked['result']['scenes'][1]
        self.assertIn('EVIDENCE_MISSING', row['codes'])
        self.assertEqual(row['states']['path_blocked']['state'], 'ACTIVE')
        b.wait("!!document.querySelector('.compact_review [data-keep-unknown]')")
        before = deepcopy(self.store.moment(self.ids[1])); jobs = len(self.store.objects('job'))
        self.assertIn('판단 보류 1개', b.evaluate("$('seq_result_status').textContent"))
        self.assertIn('판단 보류', b.evaluate("document.querySelector('.compact_review[data-code=EVIDENCE_MISSING] h3').textContent"))
        self.assertTrue(b.evaluate("[...document.querySelectorAll('#seq_current_result details')].every(d=>!d.open)"))
        self.assertEqual(b.evaluate("document.querySelectorAll('.compact_review[data-code=EVIDENCE_MISSING] .review_compact_actions [data-batch-source]').length"), 1)
        b.evaluate("document.querySelector('[data-keep-unknown]').click();true")
        self.assertIn('재검증은 필요하지 않습니다', b.evaluate("document.querySelector('.review_keep_status').textContent"))
        self.assertEqual(self.store.moment(self.ids[1]), before)
        self.assertEqual(len(self.store.objects('job')), jobs)

    def test_suggestion_stays_a_draft_until_explicit_apply_and_recheck(self):
        b = self.prepare(uncertainty=True)
        before = deepcopy(self.store.moment(self.ids[1])); jobs = len(self.store.objects('job'))
        b.evaluate("document.querySelector('.review_compact_actions [data-batch-suggestion]').click();true")
        b.wait("!$('seq_batch_review').hidden && !!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        b.wait("$('seq_review_editor').textContent.includes('수정 초안에 넣었습니다')")
        self.assertEqual(b.evaluate("document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]').value"), 'UNKNOWN')
        self.assertIn('수정 초안에 넣었습니다', b.evaluate("$('seq_review_editor').textContent"))
        self.assertEqual(self.store.moment(self.ids[1]), before)
        self.assertEqual(len(self.store.objects('job')), jobs)
        row = self.run_review(b, 'seq_apply_verify')['result']['scenes'][1]
        self.assertIn('EVIDENCE_MISSING', row['codes'])
        self.assertNotIn('LIFECYCLE_CONFLICT', row['codes'])
        self.assertEqual(row['states']['path_blocked']['state'], 'ACTIVE')

    def test_origin_edit_is_explicit_and_returns_to_current_review_without_false_completion(self):
        b = self.prepare(); before = deepcopy(self.store.moment(self.ids[0]))
        current = deepcopy(self.store.moment(self.ids[1])); jobs = len(self.store.objects('job'))
        self.assertFalse(b.evaluate("document.querySelector('[data-code=LIFECYCLE_CONFLICT] [data-review-step=\"4\"]').checkVisibility()"))
        b.evaluate("document.querySelector('[data-batch-origin]').click();true")
        b.wait("state.moment?.ordinal===0 && !!document.querySelector('[data-refine-lifecycle]')")
        b.evaluate("document.querySelector('[data-refine-lifecycle]').click();true")
        b.wait("!$('seq_batch_review').hidden")
        self.assertEqual(self.store.moment(self.ids[0]), before)
        self.run_review(b, 'seq_apply_verify')
        self.assertEqual(b.evaluate('state.moment.ordinal'), 1)
        self.assertEqual(b.evaluate('state.stage'), 1)
        self.assertIn('다시 확인', b.evaluate("$('seq_batch_feedback').textContent"))
        self.assertEqual(len(self.store.objects('job')), jobs)
        # The current scene must be reviewed explicitly after its predecessor changes.
        saved = self.store.moment(self.ids[1])
        self.assertTrue(self.service.moment(self.ids[1])['components']['sequence_coc']['stale'])
        self.assertEqual(saved['approvals'], current['approvals'])
        for kind in ('sequence_coc','sequence_constraints'):
            self.assertEqual(sequence.candidate(saved['components'][kind]['payload'],kind), sequence.candidate(current['components'][kind]['payload'],kind))

    def test_open_and_close_without_edit_keeps_normal_coc_autosave(self):
        b = self.prepare(); before = deepcopy(self.store.moment(self.ids[1]))
        self.open_compact(b, 'sequence_constraints')
        b.evaluate("[...$('seq_review_editor').querySelectorAll('button')].find(b=>b.textContent==='수정창 닫기').click();showStage(1);$('seq_explanation').value='설명 수정';$('seq_explanation').dispatchEvent(new Event('input'));flush().then(()=>true)")
        b.wait("state.moment.components.sequence_coc.payload.explanation==='설명 수정'")
        self.assertEqual(self.store.moment(self.ids[1])['components']['sequence_coc']['payload']['explanation'], '설명 수정')
        self.assertEqual(self.store.moment(self.ids[1])['components']['sequence_constraints']['payload'], before['components']['sequence_constraints']['payload'])
        self.assertTrue(b.evaluate("$('seq_batch_review').hidden"))

    def test_batch_return_to_original_accepts_original_explicitly_and_preserves_quality(self):
        b = observations.MissingObservationBrowserTest.prepare(self, existing='UNKNOWN')
        before = deepcopy(self.store.moment(self.ids[0]))
        original = before['components']['sequence_constraints']['payload']['original_candidate']
        quality = deepcopy(self.store.objects('sequence_quality'))
        # Unknown is the sole unresolved fact; a deliberate edit exposes the lifecycle conflict.
        self.open_compact(b, 'sequence_constraints', '수정 입력')
        self.change(b, 'facts[1].truth', 'TRUE')
        self.run_review(b, 'seq_apply_verify')
        self.open_compact(b, 'sequence_constraints', '관찰 사실 2')
        self.change(b, 'facts[1].truth', 'UNKNOWN')
        row = self.run_review(b, 'seq_apply_verify')['result']['scenes'][0]
        saved = self.store.moment(self.ids[0])
        payload = saved['components']['sequence_constraints']['payload']
        self.assertEqual(sequence.candidate(payload,'sequence_constraints'), original)
        self.assertEqual(payload['original_candidate'], original)
        self.assertTrue(payload['accepted_unchanged'])
        self.assertIn('sequence_constraints', saved['approvals'])
        self.assertEqual(self.store.objects('sequence_quality'), quality)
        self.assertEqual(self.service.provider.calls, ['SEQ_COC', 'SEQ_CONSTRAINTS'])
        self.assertEqual(row['states']['path_blocked']['state'], 'ACTIVE')
        self.assertIn('EVIDENCE_MISSING', row['codes'])
        self.assertNotIn('LIFECYCLE_CONFLICT', row['codes'])

    def test_a1_unresolved_link_shows_saved_sentence_and_no_fake_repair(self):
        b = self.prepare()
        payload=sequence.candidate(self.store.moment(self.ids[1])['components']['sequence_coc']['payload'],'sequence_coc')
        payload['explanation']='공사 구역 밖에서 계속 주행했다.'
        payload['reason_bindings']=[{'action_index':0,'explanation_excerpt':payload['explanation'],'reasons':[{'atom':{'predicate':'ZONE_CLOSED','subject_ref':'e2','object_ref':None},'expected_truth':'TRUE'}]}]
        edit(self.service,self.ids[1],'sequence_coc',payload);approve(self.service,self.ids[1],'sequence_coc')
        constraints=sequence.candidate(self.store.moment(self.ids[1])['components']['sequence_constraints']['payload'],'sequence_constraints')
        edit(self.service,self.ids[1],'sequence_constraints',constraints);approve(self.service,self.ids[1],'sequence_constraints')
        self.stages()
        b.evaluate('loadMoment(state.moments[1].id).then(()=>showStage(4)).then(()=>true)')
        b.wait("!!document.querySelector('[data-code=A1][data-inspection-status=UNKNOWN]')")
        before=deepcopy(self.store.moment(self.ids[1]));jobs=deepcopy(self.store.objects('job'))
        card="document.querySelector('[data-code=A1]')"
        text=b.evaluate(card+'.textContent')
        self.assertIn('공사 구역 밖에서 계속 주행했다.',text)
        self.assertIn('오류로 판정한 항목은 아닙니다',text)
        self.assertIn('현재 검사의 연결 기준',text)
        self.assertNotIn('문제 1',text)
        self.assertNotIn('수정 제안',text)
        self.assertNotIn('연결된 입력을 확인하세요',text)
        self.assertNotIn('독립 관찰 사실과 대조합니다',text)
        self.assertEqual(b.evaluate(card+".querySelectorAll('button,[data-review-step]').length"),0)
        b.evaluate("document.querySelector('[data-property-id=A1] [data-issue-link]').click();true")
        b.wait("document.activeElement.dataset.code==='A1'")
        self.assertTrue(b.evaluate(card+'.checkVisibility()'))
        self.assertIn('설명에 쓴 이유가 맞는지',b.evaluate("document.querySelector('[data-property-id=A1]').textContent"))
        self.assertNotIn('독립 관찰',b.evaluate("document.querySelector('[data-property-id=A1]').textContent"))
        self.assertEqual(self.store.moment(self.ids[1]),before)
        self.assertEqual(self.store.objects('job'),jobs)

    def test_a1_not_checked_notice_does_not_claim_an_error_or_pass(self):
        b=self.prepare()
        b.wait("!!document.querySelector('[data-inspection-status=NOT_CHECKED]')")
        text=b.evaluate("document.querySelector('[data-inspection-status=NOT_CHECKED]').textContent")
        self.assertIn('검사하지 못함',text)
        self.assertIn('미검사는 통과가 아닙니다',text)
        self.assertNotIn('문제 1',text)
        self.assertNotIn('자동 수정안',text)

    def test_external_revision_change_cannot_overwrite_saved_input(self):
        b = self.prepare(); self.open_compact(b, 'sequence_constraints')
        self.change(b, 'facts[1].truth', 'FALSE')
        payload = sequence.candidate(self.store.moment(self.ids[1])['components']['sequence_constraints']['payload'], 'sequence_constraints')
        payload['facts'][1]['evidence_note'] = '다른 작성자가 근거를 추가했습니다.'
        edit(self.service, self.ids[1], 'sequence_constraints', payload)
        saved = deepcopy(self.store.moment(self.ids[1]))
        b.evaluate('loadMoment(state.moment.id);true')
        b.wait("$('seq_batch_status').textContent.includes('다른 곳에서 바뀌었습니다')")
        self.assertTrue(b.evaluate("$('seq_apply_review').disabled && $('seq_apply_verify').disabled"))
        self.assertEqual(self.store.moment(self.ids[1]), saved)
        b.evaluate("$('seq_discard_review').click();true")
        b.wait("$('seq_batch_review').hidden")
        self.assertEqual(self.store.moment(self.ids[1]), saved)


if __name__ == '__main__':
    unittest.main()
