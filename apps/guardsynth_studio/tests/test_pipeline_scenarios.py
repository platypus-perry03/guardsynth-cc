"""User paths through generation, real SMT checks, editing and retries."""
from copy import deepcopy
import json
import time
import unittest
from unittest.mock import patch

from apps.guardsynth_studio.common import StudioError, uid
from apps.guardsynth_studio.jobs import Worker
from . import test_http_browser as http
from . import test_grounded_browser as grounded
from .test_grounded_sequence import moment


class PipelineScenariosTest(unittest.TestCase):
    setUp = http.HTTPTest.setUp
    tearDown = http.HTTPTest.tearDown
    browser_login = http.HTTPTest.browser_login
    run_button = grounded.GroundedBrowserTest.run_button

    def start(self, action='HOLD', complete=False):
        value = moment(action=action, target='e2')
        value['coc']['entities'][1]['description'] = '횡단 보행자'
        value['coc']['entities'][2]['description'] = '진입 영역'
        value['coc']['explanation'] = '보행자가 경로를 점유하여 진입을 기다렸다.' if action == 'HOLD' else '자차가 진입 영역으로 들어갔다.'
        if complete:
            value['coc']['reason_bindings'] = [{'action_index': 0, 'explanation_excerpt': value['coc']['explanation'],
                                               'reasons': deepcopy(value['constraints']['new_definitions'][0]['activation_all_of'])}]
            value['coc']['action_observation_complete'] = True
            from .test_openai_provider import OpenAIProviderTests
            vehicle = OpenAIProviderTests.vehicle_state(self)
            vehicle['samples'] = [{**vehicle['samples'][0], 'vehicle_speed_kmh': 0, 'throttle_permille': 0}]
            video = self.store.get(self.extraction, 'extraction')['video_id']
            self.service.attach_vehicle_state(video, 0, vehicle, 'reviewer', uid())
        frame = self.store.moment(self.ids[0])['frame']['frame_id']

        def evidence(data):
            if isinstance(data, dict):
                for key, child in data.items():
                    if key == 'evidence_refs':
                        data[key] = [frame]
                    else:
                        evidence(child)
            elif isinstance(data, list):
                for child in data:
                    evidence(child)
        evidence(value)
        if complete:
            value['coc']['observed_actions'][0]['evidence_refs'].append('CAN:0')

        class Provider:
            mode = 'MOCK'
            model = 'pipeline-scenario-test-only'
            fail = None

            def __init__(inner):
                inner.calls = []

            def generate(inner, kind, frames, prompt, schema, limits):
                inner.calls.append(kind)
                if inner.fail == kind:
                    raise StudioError('TEST_FAILURE', '테스트용 생성 실패')
                result = deepcopy(value['coc' if kind == 'SEQ_COC' else 'constraints'])
                return {'parsed_candidate': result, 'raw_output': json.dumps(result),
                        'model_version': inner.model, 'provider_request_id': uid()}

        self.service.provider = Provider()
        return self.browser_login()

    def approve_ui(self, b, kind):
        suffix = 'coc' if kind == 'sequence_coc' else 'constraints'
        b.evaluate(f"if(!$('seq_accept_{suffix}').disabled && !$('seq_accept_{suffix}').checked){{$('seq_accept_{suffix}').click();}}true")
        try:
            b.wait(f"!$('seq_approve_{suffix}').disabled")
        except AssertionError:
            self.fail(json.dumps(b.evaluate("({error:$('error').textContent,busy:state.busy,stage:state.stage,coc:$('seq_coc_status').textContent,constraints:$('seq_constraints_status').textContent,accept:[$('seq_accept_coc').checked,$('seq_accept_constraints').checked],moment:state.moment})"),ensure_ascii=False))
        b.evaluate(f"$('seq_approve_{suffix}').click();true")
        b.wait('!state.busy')
        self.assertEqual(b.evaluate("$('error').textContent"), '')

    def generate_pair(self, b):
        self.run_button(b, 'seq_generate_coc')
        self.approve_ui(b, 'sequence_coc')
        self.run_button(b, 'seq_generate_constraints')
        self.approve_ui(b, 'sequence_constraints')

    def derive(self, b, cnl=False):
        for button in ['seq_generate_eblc', 'seq_check'] + (['seq_generate_cnl'] if cnl else []):
            self.run_button(b, button)
        return self.store.objects('job')[-1]

    def edit_field(self, b, path, value):
        b.evaluate("(()=>{const e=[...document.querySelectorAll('[data-path]')].find(e=>e.dataset.path===" + json.dumps(path) + ");if(!e)throw new Error('Missing editable field');e.value=" + json.dumps(value) + ";e.dispatchEvent(new Event(e.tagName==='TEXTAREA'?'input':'change',{bubbles:true}));return flush().then(()=>true);})()")
        b.wait('!state.busy')
        kind = 'sequence_coc' if path.split('[')[0].split('.')[0] in ('entities','relations','observed_actions','reason_bindings','explanation','observations') else 'sequence_constraints'
        b.wait('state.moment.components.' + kind + '.payload.' + path + '===' + json.dumps(value))
        b.wait("!$('seq_resume').hidden && !$('seq_revision_status').textContent.includes('저장하고')")
        self.assertEqual(b.evaluate("$('error').textContent"), '')

    def open_issue(self, b, component, path):
        b.evaluate('showStage(4);true')
        b.wait("!!document.querySelector('#seq_current_result [data-code=ACTION_CONTRADICTION]')")
        # Select the actual user-visible repair action, using its displayed source.
        label = 'CoC' if component == 'sequence_coc' else '관찰 사실'
        if path.startswith('new_definitions'):
            label = '제약 1'
        b.evaluate("(()=>{const boxes=[...document.querySelectorAll('#seq_current_result [data-code=ACTION_CONTRADICTION] .review_source')];const box=boxes.find(e=>e.textContent.includes(" + json.dumps(label) + "));if(!box)throw new Error('Missing issue source');box.querySelector('[data-review-suggestion]').click();return true;})()")
        b.wait("!!document.querySelector('#seq_review_editor [data-path=" + json.dumps(path) + "]')")

    def test_01_normal_generated_pair_to_cnl(self):
        b = self.start(); self.generate_pair(b); self.derive(b, cnl=True)
        jobs = self.store.objects('job')
        self.assertEqual([j['kind'] for j in jobs], ['SEQ_COC', 'SEQ_CONSTRAINTS', 'SEQ_EBLC', 'SEQ_VERIFY', 'SEQ_CNL'])
        self.assertEqual(jobs[-2]['result']['scenes'][0]['status'], 'PASS')
        self.assertIn('보행자', b.evaluate("$('seq_cnl_text').textContent"))
        self.assertEqual(self.service.provider.calls, ['SEQ_COC', 'SEQ_CONSTRAINTS'])

    def test_02_constraints_edit_requires_review_then_rebuild(self):
        b = self.start(); self.generate_pair(b); self.derive(b, cnl=True)
        b.evaluate('showStage(2);true')
        self.edit_field(b, 'new_definitions[0].description', '보행자가 진입 경로를 점유하는 동안 진입을 금지한다.')
        self.assertTrue(b.evaluate("$('seq_generate_eblc').disabled"))
        self.assertIn('제약 검토', b.evaluate("$('seq_verify_guidance').textContent"))
        self.assertFalse(b.evaluate("$('seq_resume').disabled"))
        b.evaluate("$('seq_resume').click();true"); b.wait('!state.busy && state.stage===2')
        self.approve_ui(b, 'sequence_constraints')
        self.derive(b, cnl=True)
        self.assertEqual(self.store.objects('job')[-2]['result']['scenes'][0]['status'], 'PASS')

    def test_03_counterexample_coc_edit_and_constraint_reconfirmation(self):
        b = self.start('ENTER'); self.generate_pair(b); failed = self.derive(b)
        self.assertEqual(failed['result']['scenes'][0]['status'], 'CONTRADICTION')
        self.open_issue(b, 'sequence_coc', 'observed_actions[0].code')
        self.edit_field(b, 'observed_actions[0].code', 'HOLD')
        self.assertTrue(b.evaluate("$('seq_generate_eblc').disabled && $('seq_generate_cnl').disabled"))
        self.assertIn('CoC 검토', b.evaluate("$('seq_verify_guidance').textContent"))
        self.approve_ui(b, 'sequence_coc')
        self.assertIn('제약 검토', b.evaluate("$('seq_verify_guidance').textContent"))
        self.approve_ui(b, 'sequence_constraints')
        self.derive(b, cnl=True)
        self.assertEqual(self.store.objects('job')[-2]['result']['scenes'][0]['status'], 'PASS')
        self.assertEqual(failed['result']['scenes'][0]['status'], 'CONTRADICTION')

    def test_04_counterexample_constraint_fact_edit(self):
        b = self.start('ENTER'); self.generate_pair(b); self.derive(b)
        self.open_issue(b, 'sequence_constraints', 'facts[0].truth')
        self.edit_field(b, 'facts[0].truth', 'FALSE')
        self.approve_ui(b, 'sequence_constraints'); self.derive(b, cnl=True)
        self.assertNotIn('ACTION_CONTRADICTION', self.store.objects('job')[-2]['result']['scenes'][0]['codes'])
        self.assertEqual(self.store.objects('job')[-2]['result']['scenes'][0]['status'], 'REVIEW_REQUIRED')

    def test_05_repeated_edits_remove_counterexample_keep_unchecked_conditions(self):
        b = self.start('ENTER'); self.generate_pair(b); self.derive(b)
        self.open_issue(b, 'sequence_constraints', 'facts[0].truth')
        self.edit_field(b, 'facts[0].evidence_note', '현재 영상에서 보행자가 진입 경로를 점유한다.')
        self.approve_ui(b, 'sequence_constraints'); failed = self.derive(b)
        self.assertEqual(failed['result']['scenes'][0]['status'], 'CONTRADICTION')
        self.open_issue(b, 'sequence_constraints', 'facts[0].truth')
        self.edit_field(b, 'facts[0].truth', 'FALSE')
        self.edit_field(b, 'facts[0].evidence_note', '재검토한 현재 영상에서는 보행자가 경로 밖에 있다.')
        self.approve_ui(b, 'sequence_constraints'); self.derive(b, cnl=True)
        self.assertNotIn('ACTION_CONTRADICTION', self.store.objects('job')[-2]['result']['scenes'][0]['codes'])
        self.assertIn('REQUIRED_CONDITION_MISSING', self.store.objects('job')[-2]['result']['scenes'][0]['codes'])

    def test_06_regenerated_coc_removes_old_constraints(self):
        b = self.start(); self.generate_pair(b); self.derive(b, cnl=True)
        b.evaluate("showStage(1);$('seq_reset_coc').click();true")
        self.run_button(b, 'seq_generate_coc')
        self.assertNotIn('sequence_constraints', self.store.moment(self.ids[0])['components'])
        self.assertTrue(b.evaluate("$('seq_generate_eblc').disabled && $('seq_check').disabled && $('seq_generate_cnl').disabled"))
        self.approve_ui(b, 'sequence_coc')
        self.run_button(b, 'seq_generate_constraints'); self.approve_ui(b, 'sequence_constraints')
        self.derive(b, cnl=True)

    def test_07_failed_constraint_generation_can_retry(self):
        b = self.start(); self.run_button(b, 'seq_generate_coc'); self.approve_ui(b, 'sequence_coc')
        self.service.provider.fail = 'SEQ_CONSTRAINTS'
        b.evaluate("$('seq_generate_constraints').click();true")
        end = time.monotonic() + 5
        while len(self.store.objects('job')) < 2 and time.monotonic() < end: time.sleep(.05)
        Worker(self.service).run_once(); b.wait("!state.busy && $('error').textContent.length>0")
        self.assertFalse(b.evaluate("$('seq_generate_constraints').disabled"))
        self.assertNotIn('sequence_constraints', self.store.moment(self.ids[0])['components'])
        self.service.provider.fail = None
        self.run_button(b, 'seq_generate_constraints'); self.approve_ui(b, 'sequence_constraints')
        self.derive(b, cnl=True)

    def test_08_recheck_stops_on_remaining_contradiction(self):
        b = self.start('ENTER'); self.generate_pair(b); self.derive(b)
        self.open_issue(b, 'sequence_constraints', 'facts[0].truth')
        self.edit_field(b, 'facts[0].evidence_note', '근거 설명을 다시 확인했으나 경로 점유는 여전히 참이다.')
        self.approve_ui(b, 'sequence_constraints')
        b.evaluate("showStage(4);$('seq_resume').click();true")
        end = time.monotonic() + 15
        while time.monotonic() < end:
            Worker(self.service).run_once()
            if not b.evaluate('state.busy'): break
            time.sleep(.1)
        b.wait('!state.busy')
        self.assertEqual(self.store.objects('job')[-1]['kind'], 'SEQ_VERIFY')
        self.assertEqual(self.store.objects('job')[-1]['result']['scenes'][0]['status'], 'CONTRADICTION')
        self.assertEqual(b.evaluate('state.stage'), 4)
        self.assertEqual(b.evaluate("$('error').textContent"), '')

    def test_09_constraint_definition_repair_has_executable_fields(self):
        b = self.start('ENTER'); self.generate_pair(b); self.derive(b)
        self.open_issue(b, 'sequence_constraints', 'new_definitions[0].effect')
        self.edit_field(b, 'new_definitions[0].effect', 'ALLOW')
        self.approve_ui(b, 'sequence_constraints'); self.derive(b, cnl=True)
        checked = self.store.objects('job')[-2]['result']['scenes'][0]
        self.assertNotIn('ACTION_CONTRADICTION', checked['codes'])
        self.assertEqual(checked['constraints'][0]['effect'], 'ALLOW')
        self.assertEqual(checked['status'], 'REVIEW_REQUIRED')

    def test_10_reload_preserves_pending_review_and_actionable_next_step(self):
        b = self.start(); self.generate_pair(b); self.derive(b, cnl=True)
        b.evaluate('showStage(1);true')
        self.edit_field(b, 'explanation', '관찰한 행동을 다시 설명한다.')
        b.call('Page.reload'); b.wait("!!state.moment && !$('workspace').hidden")
        b.evaluate('showStage(4);true')
        b.wait("$('seq_verify_guidance').textContent.includes('CoC 검토')")
        self.assertFalse(b.evaluate("$('seq_resume').disabled"))
        self.approve_ui(b, 'sequence_coc'); self.approve_ui(b, 'sequence_constraints')
        self.derive(b, cnl=True)

    def test_11_failed_derived_jobs_refresh_buttons_and_retry(self):
        b = self.start(); self.generate_pair(b); self.derive(b, cnl=True)
        for button, reset, downstream in [('seq_generate_eblc', 'seq_reset_eblc', 'seq_check'),
                                          ('seq_check', 'seq_reset_verify', 'seq_generate_cnl'),
                                          ('seq_generate_cnl', None, None)]:
            with self.subTest(stage=button):
                if reset:
                    b.evaluate(f"$('{reset}').click();true")
                b.wait(f"!$('{button}').disabled")
                count = len(self.store.objects('job'))
                b.evaluate(f"$('{button}').click();true")
                end = time.monotonic() + 5
                while len(self.store.objects('job')) == count and time.monotonic() < end: time.sleep(.05)
                with patch('apps.guardsynth_studio.jobs.child', side_effect=StudioError('TASK_FAILED', 'Traceback internal failure for test')):
                    Worker(self.service).run_once()
                b.wait("!state.busy && $('error').textContent.length>0")
                self.assertNotIn('Traceback', b.evaluate("$('error').textContent"))
                self.assertFalse(b.evaluate(f"$('{button}').disabled"))
                if downstream:
                    self.assertTrue(b.evaluate(f"$('{downstream}').disabled"))
                self.run_button(b, button)
                if button == 'seq_generate_eblc':
                    self.run_button(b, 'seq_check'); self.run_button(b, 'seq_generate_cnl')
                elif button == 'seq_check':
                    self.run_button(b, 'seq_generate_cnl')

    def test_12_rejected_constraint_edit_can_be_corrected_without_reload(self):
        b = self.start(); self.generate_pair(b); self.derive(b, cnl=True)
        before = deepcopy(self.store.moment(self.ids[0]))
        b.evaluate("showStage(2);(()=>{const e=document.querySelector('[data-path=\"new_definitions[0].description\"]');e.value='';e.dispatchEvent(new Event('input'));return flush().catch(()=>true);})()")
        self.assertEqual(self.store.moment(self.ids[0]), before)
        self.assertTrue(b.evaluate("$('seq_generate_eblc').disabled && $('seq_generate_cnl').disabled"))
        self.edit_field(b, 'new_definitions[0].description', '보행자 경로가 겹치는 동안 진입 금지')
        self.approve_ui(b, 'sequence_constraints'); self.derive(b, cnl=True)
        self.assertEqual(b.evaluate("dbOp('getAll').then(rows=>rows.length)"), 0)

    def test_13_repaired_logic_keeps_unchecked_properties_before_explicit_cnl(self):
        b = self.start('ENTER'); self.generate_pair(b); self.derive(b)
        self.open_issue(b, 'sequence_coc', 'observed_actions[0].code')
        self.edit_field(b, 'observed_actions[0].code', 'HOLD')
        self.approve_ui(b, 'sequence_coc'); self.approve_ui(b, 'sequence_constraints')
        b.evaluate("showStage(4);$('seq_resume').click();true")
        end = time.monotonic() + 15
        while time.monotonic() < end:
            Worker(self.service).run_once()
            if not b.evaluate('state.busy'): break
            time.sleep(.1)
        b.wait('!state.busy')
        self.assertEqual([j['kind'] for j in self.store.objects('job')[-2:]], ['SEQ_EBLC', 'SEQ_VERIFY'])
        self.assertEqual(self.store.objects('job')[-1]['result']['scenes'][0]['status'], 'PASS')
        self.assertIn('CNL 초안', b.evaluate("$('seq_generate_cnl').textContent"))
        self.run_button(b, 'seq_generate_cnl')
        self.assertEqual(b.evaluate("$('error').textContent"), '')

    def test_14_complete_reason_and_can_inputs_resume_to_cnl(self):
        b = self.start(complete=True); self.generate_pair(b); self.derive(b)
        b.evaluate('showStage(2);true')
        self.edit_field(b, 'new_definitions[0].description', '보행자가 경로를 점유하므로 진입 금지')
        self.approve_ui(b, 'sequence_constraints')
        b.evaluate("showStage(4);$('seq_resume').click();true")
        end = time.monotonic() + 15
        while time.monotonic() < end:
            Worker(self.service).run_once()
            if not b.evaluate('state.busy'): break
            time.sleep(.1)
        b.wait('!state.busy')
        if self.store.objects('job')[-1]['kind'] != 'SEQ_CNL':
            checked = self.store.objects('job')[-1]['result']['scenes'][0]
            self.fail(json.dumps({'codes': checked['codes'], 'properties': checked['properties']['results']},ensure_ascii=False))
        self.assertEqual([j['kind'] for j in self.store.objects('job')[-3:]], ['SEQ_EBLC', 'SEQ_VERIFY', 'SEQ_CNL'])
        properties = self.store.objects('job')[-2]['result']['scenes'][0]['properties']['results']
        self.assertTrue(all(p['status'] in ('PASS', 'NOT_APPLICABLE') for p in properties))
        self.assertEqual(b.evaluate("$('error').textContent"), '')
