"""Browser flow from regenerated CoC to a fresh downstream pipeline."""
from copy import deepcopy
import unittest

from . import test_grounded_browser as grounded
from . import test_http_browser as http
from .test_grounded_sequence import definition
from .helpers import approve


class GenerationResetBrowserTest(unittest.TestCase):
    setUp=http.HTTPTest.setUp
    tearDown=http.HTTPTest.tearDown
    browser_login=http.HTTPTest.browser_login
    coc_candidate=grounded.GroundedBrowserTest.coc_candidate
    install_coc=grounded.GroundedBrowserTest.install_coc
    install_button_pair=grounded.GroundedBrowserTest.install_button_pair
    run_button=grounded.GroundedBrowserTest.run_button

    def test_regenerated_coc_requires_new_constraints_and_all_derived_steps(self):
        self.install_button_pair();b=self.browser_login()
        for button in ('seq_generate_eblc','seq_check','seq_generate_cnl'):self.run_button(b,button)
        b.evaluate("$('seq_reset_coc').click();true");self.run_button(b,'seq_generate_coc')
        b.wait("!state.moment.components.sequence_constraints && $('seq_approve_constraints').disabled")
        self.assertTrue(b.evaluate("$('seq_generate_constraints').disabled && $('seq_generate_eblc').disabled && $('seq_check').disabled && $('seq_generate_cnl').disabled"))
        self.assertNotIn('sequence_constraints',self.store.moment(self.ids[0])['components'])
        b.evaluate("$('seq_accept_coc').checked=true;$('seq_accept_coc').dispatchEvent(new Event('change'));flush().then(()=>true)")
        b.wait("!$('seq_approve_coc').disabled")
        b.evaluate("$('seq_approve_coc').click();true")
        b.wait("!state.busy && !$('seq_generate_constraints').disabled && $('seq_reset_constraints').hidden")
        self.run_button(b,'seq_generate_constraints')
        b.evaluate("$('seq_accept_constraints').checked=true;$('seq_accept_constraints').dispatchEvent(new Event('change'));flush().then(()=>true)")
        b.wait("!$('seq_approve_constraints').disabled")
        b.evaluate("$('seq_approve_constraints').click();true")
        b.wait("!state.busy && !$('seq_generate_eblc').disabled")
        self.assertTrue(b.evaluate("$('seq_check').disabled && $('seq_generate_cnl').disabled"))
        for button in ('seq_generate_eblc','seq_check','seq_generate_cnl'):self.run_button(b,button)
        self.assertEqual(self.service.provider.calls,['SEQ_COC','SEQ_CONSTRAINTS'])
        self.assertEqual(b.evaluate("$('error').textContent"),'')

    def test_old_missing_target_is_history_and_fresh_generation_needs_no_reset(self):
        self.install_button_pair()
        with self.store.transaction():
            m=self.store.moment(self.ids[0]);coc=deepcopy(m['components']['sequence_coc']['payload']);coc['generation_job_id']='new-coc-generation'
            old=deepcopy(m['components']['sequence_constraints']['payload'])
            old['original_coc_generation_id']='old-coc-generation'
            d=definition();d['condition_target_refs']=['e1','e4'];old['new_definitions']=[d]
            self.store.install(m,'sequence_coc',coc);self.store.install(m,'sequence_constraints',old);self.store.save(m,'old stored generation fixture')
        approve(self.service,self.ids[0],'sequence_coc')
        before=deepcopy(self.store.moment(self.ids[0]));b=self.browser_login();b.evaluate('showStage(2);true')
        b.wait("!!document.querySelector('[data-generation-gap]')")
        self.assertFalse(b.evaluate("$('seq_generate_constraints').disabled"))
        self.assertTrue(b.evaluate("$('seq_accept_constraints').disabled && $('seq_approve_constraints').disabled && $('seq_reset_constraints').hidden"))
        self.assertEqual(b.evaluate("document.querySelectorAll('#seq_candidates input,#seq_candidates select,#seq_candidates textarea,#seq_candidates button').length"),0)
        self.assertEqual(self.store.moment(self.ids[0]),before)
        self.run_button(b,'seq_generate_constraints')
        b.wait("!document.querySelector('[data-generation-gap]')")
        self.assertEqual(b.evaluate("$('error').textContent"),'')
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['new_definitions'],[])
