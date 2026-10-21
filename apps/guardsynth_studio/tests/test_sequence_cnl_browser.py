"""The final Studio output displays CoC plus CNL and a separate verdict disclosure."""
from copy import deepcopy
import unittest

from . import test_http_browser as http
from . import test_postcondition_review_browser as postcondition
from . import test_pipeline_scenarios as scenarios


class SequenceCNLBrowserTest(unittest.TestCase):
    setUp = http.HTTPTest.setUp
    tearDown = http.HTTPTest.tearDown
    browser_login = http.HTTPTest.browser_login
    stages = postcondition.PostconditionReviewBrowserTest.stages
    prepare = postcondition.PostconditionReviewBrowserTest.prepare
    run_button = scenarios.PipelineScenariosTest.run_button

    def test_cnl_content_report_and_stale_disclosure(self):
        b = self.prepare(action='CONTINUE')
        before = deepcopy(self.store.moment(self.ids[0]))
        self.run_button(b, 'seq_generate_cnl')
        b.evaluate('showStage(5);true')
        text = b.evaluate("$('seq_cnl_text').textContent")
        self.assertIn(before['components']['sequence_coc']['payload']['explanation'], text)
        self.assertIn('제약 사항', text)
        self.assertIn('금지한다', text)
        self.assertNotIn('행동 제약:', text)
        self.assertNotIn('행동 뒤 기대 결과:', text)
        self.assertFalse(b.evaluate("$('seq_cnl_details').hidden"))
        self.assertFalse(b.evaluate("$('seq_cnl_details').open"))
        b.evaluate("$('seq_cnl_details').open=true;true")
        self.assertIn('행동 뒤 기대 결과:',b.evaluate("$('seq_cnl_details_text').textContent"))
        self.assertNotIn('검증 상태:', text)
        self.assertNotIn('12개 속성:', text)
        self.assertFalse(b.evaluate("$('seq_cnl_verification').hidden"))
        self.assertIn('검증 상태:', b.evaluate("$('seq_cnl_verification_text').textContent"))
        self.assertIn('12개 속성:', b.evaluate("$('seq_cnl_verification_text').textContent"))
        self.assertEqual(self.store.moment(self.ids[0]), before)
        b.evaluate("showStage(1);$('seq_explanation').value='검토한 주행 설명을 수정함';$('seq_explanation').dispatchEvent(new Event('input',{bubbles:true}));flush().then(()=>true)")
        b.wait("$('seq_cnl_verification').hidden && $('seq_cnl_verification_text').textContent==='' && $('seq_cnl_text').textContent.includes('입력이 바뀌었습니다')")
        b.wait("!state.busy && $('save_state').textContent==='저장됨'")
        self.assertTrue(b.evaluate("$('seq_cnl_details').hidden && !$('seq_cnl_details').open && $('seq_cnl_details_text').textContent===''"))


if __name__ == '__main__':
    unittest.main()
