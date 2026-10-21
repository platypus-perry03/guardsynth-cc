"""An inherited definition must not redirect a current observation correction."""
from copy import deepcopy
import threading
import unittest

from apps.guardsynth_studio import sequence
from apps.guardsynth_studio.jobs import Worker
from . import test_http_browser as http
from . import test_pipeline_scenarios as scenarios
from . import test_studio_properties_browser as properties
from .helpers import edit, approve
from .test_grounded_sequence import moment, definition, guard, fact


class LifecycleCorrectionBrowserTest(unittest.TestCase):
    setUp = http.HTTPTest.setUp
    tearDown = http.HTTPTest.tearDown
    browser_login = http.HTTPTest.browser_login
    stages = properties.StudioPropertiesBrowserTest.stages
    edit_field = scenarios.PipelineScenariosTest.edit_field
    approve_ui = scenarios.PipelineScenariosTest.approve_ui

    def prepare(self, uncertainty=False, duplicate=False):
        d = definition(condition_class='WORKZONE_OBSTACLE',
                       description='우측 공사 구역은 자차 진입 금지 후보로 본다.',
                       activation_all_of=[guard(predicate='ZONE_CLOSED', subject='e2', target=None)],
                       release_any_of=[guard(predicate='PASSAGE_COMPLETE', subject='ego', target='e2')])
        closed = fact(predicate='ZONE_CLOSED', subject='e2', target=None)
        passed = fact(predicate='PASSAGE_COMPLETE', subject='ego', target='e2')
        ms = [moment(0, [d], [closed, {**passed, 'truth': 'FALSE'}], action='CONTINUE'),
              moment(1, [], [closed, passed], action='CONTINUE', previous=True)]
        if uncertainty:
            ms[1]['constraints']['facts'][1]['evidence_note'] = '통과 완료 여부는 현재 영상만으로 확인되지 않는다.'
        if duplicate:
            ms[1]['coc']['relations'] = [{**passed['atom'], 'truth': 'FALSE', 'evidence_refs': ['f']}]
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
        b = self.browser_login()
        b.evaluate('loadMoment(state.moments[1].id).then(()=>render()).then(()=>showStage(4));true')
        b.wait("!!document.querySelector('#seq_current_result [data-code=LIFECYCLE_CONFLICT] [data-lifecycle-observation=PASSAGE_COMPLETE]')")
        return b

    def recheck(self, b, selector='[data-review-recheck]'):
        stopped = threading.Event()

        def worker():
            while not stopped.is_set():
                Worker(self.service).run_once(); stopped.wait(.02)
        runner = threading.Thread(target=worker, daemon=True); runner.start()
        before = len(self.store.objects('job'))
        try:
            b.evaluate("document.querySelector(" + repr(selector) + ").click();true")
            b.wait("!state.busy && state.moment.ordinal===1 && !$('seq_check').textContent.includes('실행 중')")
            self.assertEqual(b.evaluate("$('error').textContent"), '')
            self.assertGreaterEqual(len(self.store.objects('job')), before + 2)
        finally:
            stopped.set(); runner.join(timeout=10)
        return sequence.latest_stage(self.service, self.extraction, 'SEQ_VERIFY')['result']['scenes'][1]

    def test_current_passage_edit_rechecks_current_scene_and_preserves_origin(self):
        b = self.prepare()
        origin = deepcopy(self.store.moment(self.ids[0]))
        text = b.evaluate("document.querySelector('#seq_current_result [data-code=LIFECYCLE_CONFLICT]').textContent")
        self.assertIn('조건 시작', text); self.assertIn('조건 해제', text)
        self.assertIn('원래 제약 정의 수정', text)
        b.evaluate("document.querySelector('#seq_current_result [data-lifecycle-observation=PASSAGE_COMPLETE]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        self.assertEqual(b.evaluate('state.moment.ordinal'), 1)
        self.assertIn('시점 2', b.evaluate("$('seq_review_editor').textContent"))
        self.edit_field(b, 'facts[1].truth', 'FALSE')
        self.edit_field(b, 'facts[1].evidence_note', '현재 영상에서 아직 공사 구역 옆을 지나가는 중이다.')
        b.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').click();true")
        b.wait('!state.busy && !!state.moment.approvals.sequence_constraints')
        row = self.recheck(b)
        self.assertEqual(row['states']['path_blocked']['state'], 'ACTIVE')
        self.assertNotIn('LIFECYCLE_CONFLICT', row['codes'])
        self.assertEqual(self.store.moment(self.ids[0]), origin)

    def test_uncertainty_suggestion_stays_current_and_retains_obligation(self):
        b = self.prepare(uncertainty=True)
        origin = deepcopy(self.store.moment(self.ids[0]))
        b.evaluate("document.querySelector('#seq_current_result [data-code=LIFECYCLE_CONFLICT] [data-accept-suggestion]').click();true")
        b.wait("state.moment.ordinal===1 && state.moment.components.sequence_constraints.payload.facts[1].truth==='UNKNOWN'")
        b.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').click();true")
        b.wait('!state.busy && !!state.moment.approvals.sequence_constraints')
        row = self.recheck(b)
        self.assertEqual(row['states']['path_blocked']['state'], 'ACTIVE')
        self.assertIn('EVIDENCE_MISSING', row['codes'])
        self.assertNotIn('LIFECYCLE_CONFLICT', row['codes'])
        self.assertEqual(self.store.moment(self.ids[0]), origin)

    def test_origin_open_and_return_do_not_modify_inputs(self):
        b = self.prepare(); before = [deepcopy(self.store.moment(i)) for i in self.ids[:2]]
        b.evaluate("[...document.querySelector('[data-code=LIFECYCLE_CONFLICT]').querySelectorAll('button')].find(e=>e.textContent==='원래 제약 정의 수정').click();true")
        b.wait('state.moment.ordinal===0 && !!document.querySelector("[data-review-return]")')
        self.assertIn('시점 1', b.evaluate("$('seq_review_editor').textContent"))
        b.evaluate("document.querySelector('[data-review-return]').click();true")
        b.wait("state.moment.ordinal===1 && !!document.querySelector('#seq_current_result [data-lifecycle-observation=PASSAGE_COMPLETE]')")
        self.assertEqual([self.store.moment(i) for i in self.ids[:2]], before)
        b.call('Page.reload')
        b.wait("state.moment?.ordinal===1 && !!document.querySelector('#seq_current_result [data-lifecycle-observation=PASSAGE_COMPLETE]')")
        b.evaluate("document.querySelector('#seq_current_result [data-lifecycle-observation=PASSAGE_COMPLETE]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"facts[1].truth\"]')")
        self.assertEqual(b.evaluate('state.moment.ordinal'), 1)

    def test_origin_applicability_refinement_returns_for_current_recheck(self):
        b = self.prepare(); current = deepcopy(self.store.moment(self.ids[1]))
        b.evaluate("[...document.querySelector('[data-code=LIFECYCLE_CONFLICT]').querySelectorAll('button')].find(e=>e.textContent==='원래 제약 정의 수정').click();true")
        b.wait('state.moment.ordinal===0 && !!document.querySelector("[data-refine-lifecycle]")')
        b.evaluate("document.querySelector('[data-refine-lifecycle]').click();true")
        b.wait("state.moment.components.sequence_constraints.payload.new_definitions[0].activation_all_of.length===2 && !$('seq_revision_status').textContent.includes('저장하고')")
        self.assertFalse(b.evaluate("!!document.querySelector('[data-refine-lifecycle]')"))
        b.evaluate("document.querySelector('[data-review-approve=sequence_constraints]').click();true")
        b.wait('!state.busy && !!state.moment.approvals.sequence_constraints')
        jobs = len(self.store.objects('job'))
        b.evaluate("document.querySelector('[data-review-recheck]').click();true")
        b.wait('!state.busy && state.moment.ordinal===1 && state.stage===1')
        self.assertEqual(b.evaluate("$('error').textContent"), '')
        self.assertEqual(len(self.store.objects('job')), jobs)
        # Editing an earlier definition invalidates later approvals. Review is explicit.
        self.approve_ui(b, 'sequence_coc')
        self.approve_ui(b, 'sequence_constraints')
        b.evaluate('showStage(4);true')
        row = self.recheck(b, '#seq_resume')
        self.assertEqual(row['states']['path_blocked']['state'], 'RELEASED')
        self.assertNotIn('LIFECYCLE_CONFLICT', row['codes'])
        for kind in ('sequence_coc', 'sequence_constraints'):
            self.assertEqual(sequence.candidate(self.store.moment(self.ids[1])['components'][kind]['payload'],kind),
                             sequence.candidate(current['components'][kind]['payload'],kind))

    def test_conflicting_current_coc_and_constraint_are_both_editable(self):
        b = self.prepare(duplicate=True)
        components = b.evaluate("[...document.querySelectorAll('#seq_current_result [data-lifecycle-observation=PASSAGE_COMPLETE]')].map(e=>e.dataset.observationComponent)")
        self.assertEqual(set(components), {'sequence_coc', 'sequence_constraints'})
        b.evaluate("document.querySelector('#seq_current_result [data-lifecycle-observation=PASSAGE_COMPLETE][data-observation-component=sequence_coc]').click();true")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=\"relations[0].truth\"]')")
        self.assertEqual(b.evaluate('state.moment.ordinal'), 1)


if __name__ == '__main__':
    unittest.main()
