"""CoC plus controlled constraints is the CNL; verification is separate metadata."""
from copy import deepcopy
import unittest

from guard_synth.studio_sequence import compile_sequence, verify_compiled, render_verified
from guard_synth.studio_grounded_sequence import render_grounded_constraints
from guard_synth.studio_relations import RULES
from .test_grounded_sequence import moment, definition, guard, fact


class SequenceCNLTest(unittest.TestCase):
    def render(self, moments):
        compiled = compile_sequence(moments, {'sources': []})
        return render_verified(compiled, verify_compiled(compiled))['samples']

    def test_cnl_contains_reviewed_coc_and_named_constraints_without_report(self):
        d = definition(condition_class='WORKZONE_OBSTACLE', description='우측 공사 구역 진입 금지',
                       activation_all_of=[guard(predicate='ZONE_CLOSED', subject='e2', target=None)],
                       release_any_of=[guard(predicate='PASSAGE_COMPLETE', subject='ego', target='e2')],
                       expected_postconditions=[guard('FALSE', predicate='IN', subject='ego', target='e2')])
        m = moment(definitions=[d], facts=[fact(predicate='ZONE_CLOSED', subject='e2', target=None),
                                         fact('FALSE', predicate='PASSAGE_COMPLETE', subject='ego', target='e2')], action='CONTINUE')
        m['coc']['explanation'] = '자차는 좌측으로 굽은 차로를 따라 계속 주행한 것으로 보인다.'
        m['coc']['entities'][2]['description'] = '우측 바리케이드 안쪽 공사 구역'
        before = deepcopy(m); sample = self.render([m])[0]
        self.assertTrue(sample['text'].startswith('CoC\n' + m['coc']['explanation']))
        for text in ['제약 사항', '우측 바리케이드 안쪽 공사 구역', '금지한다', '통행 차단', '통과 완료', '그 전까지 유지한다']:
            self.assertIn(text, sample['text'])
        for technical in ['ZONE_CLOSED', 'PASSAGE_COMPLETE', 'IN(ego', '(e2)', '검증 상태:', '12개 속성:']:
            self.assertNotIn(technical, sample['text'])
        self.assertIn('검증 상태:', sample['verification_text'])
        self.assertIn('12개 속성:', sample['verification_text'])
        self.assertIn('미검사는 통과가 아닙니다', sample['verification_text'])
        self.assertEqual(sample['combined'], sample['text'])
        self.assertEqual(sample['text'].count('우측 바리케이드 안쪽 공사 구역'),1)
        self.assertNotIn('행동 뒤 기대 결과:', sample['text'])
        self.assertNotIn('기대 결과 확인 시점:', sample['text'])
        self.assertIn('행동 뒤 기대 결과:', sample['constraint_details'])
        self.assertIn('성립하지 않음', sample['constraint_details'])
        self.assertEqual(m, before)

    def test_carried_definition_uses_previous_scene_name(self):
        a = moment(); a['coc']['entities'][2]['description'] = '교차로 진입 구역'
        b = moment(1, [], [fact()], previous=True)
        b['coc']['entities'] = [e for e in b['coc']['entities'] if e['entity_id'] != 'e2']
        sample = self.render([a, b])[1]
        self.assertIn(b['coc']['explanation'], sample['text'])
        self.assertIn('교차로 진입 구역', sample['text'])
        self.assertIn('시점 1에서 이어받은 제약', sample['text'])

    def test_carried_target_is_not_renamed_by_unrelated_previous_scene(self):
        a=moment(10)
        a['coc']['entities'][2]['description']='우측 바리케이드 공사 구역'
        gap=moment(15,[],[])
        gap['constraints']={}
        gap['coc']['entities'][2].update(kind='LANE',description='자차가 주행 중인 좌측 차로')
        b=moment(16,[],[])
        b['coc']['entities']=b['coc']['entities'][:1]
        before=deepcopy([a,gap,b]);sample=self.render([a,gap,b])[-1]
        self.assertIn('우측 바리케이드 공사 구역',sample['text'])
        self.assertNotIn('좌측 차로',sample['text'])
        self.assertNotIn('좌측 차로',sample['constraint_details'])
        self.assertIn('시점 11에서 이어받은 제약',sample['text'])
        self.assertEqual([a,gap,b],before)

    def test_continuation_cnl_uses_retained_target_without_original_scene(self):
        from guard_synth.studio_grounded_sequence import compile_grounded_sequence
        a=moment();a['coc']['entities'][2]['description']='화면 밖의 공사 구역'
        summary=compile_grounded_sequence([a],{'sources':[]})['continuation_summary']
        b=moment(4,[],[]);b['coc']['entities']=b['coc']['entities'][:1]
        compiled=compile_grounded_sequence([b],{'sources':[]},summary)
        sample=render_verified(compiled,verify_compiled(compiled))['samples'][0]
        self.assertIn('화면 밖의 공사 구역',sample['text'])
        self.assertNotIn('연결이 확인되지 않은 대상',sample['constraint_details'])

    def test_unknown_and_contradictory_verdicts_do_not_rewrite_coc(self):
        for m in [moment(action='ENTER', target='e2'), moment(facts=[fact('UNKNOWN')])]:
            sample = self.render([m])[0]
            self.assertIn(m['coc']['explanation'], sample['text'])
            self.assertNotIn('검증 상태:', sample['text'])
            self.assertIn('모순 발견' if sample['status'] == 'CONTRADICTION' else '추가 확인 필요', sample['verification_text'])

    def test_all_supported_predicates_and_signed_conditions_are_readable(self):
        labels = {'e1': '전방 대상', 'e2': '주행 차로'}
        for predicate in RULES:
            d = definition(activation_all_of=[guard(predicate=predicate)],
                           release_any_of=[guard('FALSE', predicate=predicate)])
            text = render_grounded_constraints([d], labels,detailed=True)
            self.assertNotIn(predicate + '(', text)
            self.assertNotIn('지원하지 않는 관계', text)
            self.assertIn('모두 확인되면', text)
            self.assertIn('하나 이상이 확인되면', text)
            self.assertIn('성립하지 않음', text)

    def test_no_constraint_and_missing_label_are_explicit_without_fabrication(self):
        m = moment(definitions=[]); sample = self.render([m])[0]
        self.assertIn('생성된 제약이 없습니다', sample['text'])
        text = render_grounded_constraints([definition()])
        self.assertIn('연결이 확인되지 않은 대상', text)
        self.assertNotIn('e2', text)

    def test_compact_rules_retain_conjunction_disjunction_negative_and_preconditions(self):
        d=definition(activation_all_of=[guard(),guard('FALSE',predicate='IN',subject='ego',target='e2')],
                     release_any_of=[guard('FALSE'),guard(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')],
                     preconditions=[guard(predicate='PATH_CLEAR',subject='e2',target=None)])
        text=render_grounded_constraints([d],{'e1':'보행자','e2':'교차로'})
        for phrase in ('조건이 모두','하나라도','아니라는 사실','행동 전','모두 확인해야','그 전까지 유지'):
            self.assertIn(phrase,text)


if __name__ == '__main__':
    unittest.main()
