"""Presentation must preserve raw verdicts while separating missing input and sources."""
from copy import deepcopy
import unittest

from apps.guardsynth_studio.common import digest
from apps.guardsynth_studio.review_summary import summarize, correction_review


def snapshot_moment(i,authored=False,actions=None):
    components={};approvals={}
    if authored:
        for kind,payload in [('sequence_coc',{'explanation':'기록된 행동 설명','observed_actions':actions if actions is not None else []}),('sequence_constraints',{'constraints':[]})]:
            components[kind]={'id':kind+str(i),'payload':payload,'dependencies':{},'stale':False}
            approvals[kind]={'decision':'APPROVE','component_id':kind+str(i),'dependency_digest':digest({})}
    return {'id':'m'+str(i),'ordinal':i,'components':components,'approvals':approvals}


class ReviewSummaryTest(unittest.TestCase):
    def test_offscreen_target_name_comes_from_definition_metadata(self):
        from apps.guardsynth_studio.review_summary import unified_issues
        from .test_grounded_sequence import fact
        f=fact('UNKNOWN',predicate='PASSAGE_COMPLETE',subject='ego',target='e2')
        issue={'code':'EVIDENCE_MISSING','message':'현재 통과 여부를 확인하세요.','sources':[{'moment_id':'m2','component':'sequence_constraints','path':'/facts/0','value':f}]}
        inputs={'m2':{'id':'m2','components':{'sequence_coc':{'payload':{'entities':[{'entity_id':'ego','kind':'EGO','description':'자차'}]}},'sequence_constraints':{'payload':{'facts':[f]}}}}}
        models={'m2':{'property_input':{'inherited_entities':[{'entity_id':'e2','kind':'ZONE','description':'이전 장면의 공사 구역'}]}}}
        items,_=unified_issues([issue],{},inputs,models)
        self.assertEqual(items[0]['sources'][0]['entity_labels']['e2'],'이전 장면의 공사 구역')
        self.assertEqual(items[0]['sources'][0]['entity_kinds']['e2'],'ZONE')

    def test_lifecycle_uncertainty_candidate_targets_current_fact_only(self):
        from apps.guardsynth_studio.review_summary import unified_issues
        from .test_grounded_sequence import moment,definition,fact,guard
        d=definition(release_any_of=[guard(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')])
        f=fact(predicate='PASSAGE_COMPLETE',subject='ego',target='e2')
        f['evidence_note']='통과 완료 여부는 현재 화면만으로 확인되지 않는다.'
        inputs={}
        for index in (10,11):
            m=moment(index);inputs[m['id']]={'id':m['id'],'revision':4,'components':{'sequence_coc':{'payload':m['coc']},'sequence_constraints':{'payload':m['constraints']}}}
        sources=[{'moment_id':'m10','component':'sequence_constraints','path':'/new_definitions/0','value':d},
                 {'moment_id':'m11','component':'sequence_constraints','path':'/facts/0','value':f}]
        issue={'code':'LIFECYCLE_CONFLICT','message':'conflict','sources':sources}
        before=deepcopy((issue,inputs))
        properties={'results':[{'property_id':'B5','status':'FAIL','checks':[issue]}]}
        items,links=unified_issues([issue],properties,inputs)
        self.assertEqual(len(items),1)
        self.assertEqual(links['B5'],[items[0]['issue_id']])
        suggestion=items[0]['suggestions'][0]
        self.assertEqual((suggestion['source']['moment_id'],suggestion['before'],suggestion['value']),('m11','TRUE','UNKNOWN'))
        self.assertIn('현재 시점',items[0]['guidance'])
        self.assertEqual((issue,inputs),before)

    def test_corrections_compare_saved_input_and_never_resolve_a_stale_check(self):
        compiled,result,snapshot=self.fixture()
        source={'moment_id':'m10','component':'sequence_constraints','path':'/constraints/0','value':deepcopy(snapshot['moments'][10]['components']['sequence_constraints']['payload']['constraints'][0])}
        result['scenes'][10]['review_items']=[{'code':'UNSUPPORTED_ATOM','message':'대상 연결 확인','sources':[source]}]
        baseline={'id':'old-check','inputs':{'snapshot':deepcopy(snapshot),'compiled':deepcopy(compiled)},'result':deepcopy(result)}
        snapshot['moments'][10]['components']['sequence_constraints']['payload']['constraints'][0]['truth']='FALSE'
        before=deepcopy((baseline,snapshot));review=correction_review(baseline,baseline,snapshot,None,True)
        self.assertEqual(review['changed_inputs'][0]['component'],'sequence_constraints')
        self.assertTrue(all(i['status']=='PENDING' for i in review['issues']))
        current=summarize(compiled,result,snapshot)
        review=correction_review(baseline,{'id':'new-check'},snapshot,current,False)
        self.assertEqual(next(i for i in review['issues'] if i['code']=='UNSUPPORTED_ATOM')['status'],'STILL_PRESENT')
        result['scenes'][10]['review_items']=[];result['scenes'][10]['codes']=[]
        current=summarize(compiled,result,snapshot)
        review=correction_review(baseline,{'id':'new-check'},snapshot,current,False)
        self.assertEqual(next(i for i in review['issues'] if i['code']=='UNSUPPORTED_ATOM')['status'],'NOT_EVALUATED')
        snapshot['moments'][10]['components']['sequence_coc']['payload']['observed_actions']=['CONTINUE']
        current=summarize(compiled,result,snapshot)
        review=correction_review(baseline,{'id':'new-check'},snapshot,current,False)
        self.assertEqual(next(i for i in review['issues'] if i['code']=='UNSUPPORTED_ATOM')['status'],'NOT_REPORTED')
        self.assertEqual(baseline,before[0])

    def fixture(self):
        snapshots=[snapshot_moment(i,i==10) for i in range(21)]
        signal={'condition_id':'signal_applies','description':'자차 경로에 적용되는 신호','truth':'UNKNOWN','scope_state':'UNKNOWN','evidence_refs':['f'],'evidence_note':'신호 적용성 미확인'}
        snapshots[10]['components']['sequence_constraints']['payload']['constraints']=[signal]
        compiled={'scenes':[{'moment_id':'m'+str(i),'ordinal':i,'constraints':[signal] if i>=10 else [],'observed_actions':[],'ledger':{'signal_applies':'UNKNOWN'} if i>=10 else {}} for i in range(21)]}
        result={'status':'REVIEW_REQUIRED','scenes':[{'moment_id':'m'+str(i),'ordinal':i,'status':'REVIEW_REQUIRED','codes':['CATALOG_MISSING','REVIEW_REQUIRED']+(['EVIDENCE_MISSING','UNGROUNDED'] if i>=10 else [])} for i in range(21)],'pairs':[{'from_ordinal':i,'to_ordinal':i+1,'carried_ids':['signal_applies'] if i>=10 else [],'status':'REVIEW_REQUIRED','codes':['CATALOG_MISSING','REVIEW_REQUIRED','EVIDENCE_MISSING']} for i in range(20)]}
        return compiled,result,{'moments':snapshots}

    def test_21_scene_report_has_one_source_notice_and_one_authored_scene(self):
        compiled,result,snapshot=self.fixture();before=deepcopy((compiled,result,snapshot))
        summary=summarize(compiled,result,snapshot)
        self.assertEqual(summary['counts']['authored'],1)
        self.assertEqual(summary['counts']['not_created'],20)
        self.assertEqual(summary['counts']['pending_pairs'],20)
        self.assertEqual(len(summary['source_notices']),1)
        authored=next(s for s in summary['scenes'] if s['ordinal']==10)
        self.assertEqual({x['code'] for x in authored['issues']},{'MISSING_OBSERVED_ACTION','EVIDENCE_MISSING'})
        self.assertEqual(authored['issues'][1]['sources'][0]['path'],'/constraints/0/scope_state')
        self.assertEqual(len(summary['scene_groups']),3)
        self.assertEqual(len(summary['pair_groups']),2)
        self.assertTrue(all(g['status']=='WAITING' for g in summary['pair_groups']))
        self.assertEqual((compiled,result,snapshot),before)

    def test_reviewed_empty_actions_are_not_treated_as_complete_or_pair_pass(self):
        compiled,result,snapshot=self.fixture();s=summarize(compiled,result,snapshot)
        self.assertEqual(s['counts']['ready'],0)
        self.assertEqual(s['counts']['checked_pairs'],0)
        self.assertEqual(s['scenes'][10]['input_status'],'ACTION_NEEDED')

    def test_two_ready_scenes_keep_counterexamples_and_source_review_separate(self):
        compiled,result,snapshot=self.fixture()
        for i in (10,11):snapshot['moments'][i]=snapshot_moment(i,True,['HOLD'])
        result['scenes'][10]['codes']=['CATALOG_MISSING','UNGROUNDED']
        result['scenes'][11]['status']='CONTRADICTION';result['scenes'][11]['codes']=['CATALOG_MISSING','ACTION_CONTRADICTION']
        result['pairs'][10]['status']='CONTRADICTION';result['pairs'][10]['codes']=['CATALOG_MISSING','ACTION_CONTRADICTION']
        s=summarize(compiled,result,snapshot)
        self.assertEqual(s['counts']['checked_pairs'],1)
        self.assertEqual(s['scenes'][10]['display_status'],'SOURCE_REVIEW')
        self.assertEqual(s['scenes'][11]['display_status'],'CONTRADICTION')
        pair=next(g for g in s['pair_groups'] if g['status']=='CONTRADICTION')
        self.assertEqual(pair['codes'],['ACTION_CONTRADICTION'])

    def test_missing_input_does_not_hide_a_rule_contradiction(self):
        compiled,result,snapshot=self.fixture()
        result['scenes'][11]['status']='CONTRADICTION';result['scenes'][11]['codes']=['REVIEW_REQUIRED','RULE_CONTRADICTION']
        s=summarize(compiled,result,snapshot)
        self.assertEqual(s['scenes'][11]['display_status'],'CONTRADICTION')
        self.assertEqual(s['scenes'][11]['issues'][0]['code'],'RULE_CONTRADICTION')

    def test_approval_revision_and_partial_input_remain_actionable(self):
        compiled,result,snapshot=self.fixture()
        snapshot['moments'][10]['components']['sequence_coc']['payload']['observed_actions']=['CONTINUE']
        snapshot['moments'][10]['approvals']['sequence_constraints']['component_id']='old'
        del snapshot['moments'][9]['components'];snapshot['moments'][9]['components']={'sequence_coc':deepcopy(snapshot['moments'][10]['components']['sequence_coc'])}
        s=summarize(compiled,result,snapshot)
        self.assertEqual(s['scenes'][10]['input_status'],'REVIEW_NEEDED')
        self.assertIn('UNREVIEWED_CONSTRAINTS',[i['code'] for i in s['scenes'][10]['issues']])
        self.assertEqual(s['scenes'][9]['input_status'],'PARTIAL')


    def test_source_only_pair_is_not_presented_as_a_logic_failure_or_full_pass(self):
        compiled,result,snapshot=self.fixture()
        for i in (10,11):
            snapshot['moments'][i]=snapshot_moment(i,True,['HOLD'])
            result['scenes'][i]['codes']=['CATALOG_MISSING']
        result['pairs'][10]['codes']=['CATALOG_MISSING']
        s=summarize(compiled,result,snapshot)
        pair=next(g for g in s['pair_groups'] if g['ready'])
        self.assertEqual(pair['status'],'SOURCE_REVIEW')
        self.assertEqual(result['pairs'][10]['status'],'REVIEW_REQUIRED')

    def test_unchanged_warnings_do_not_merge_different_lifecycle_states(self):
        compiled,result,snapshot=self.fixture()
        compiled['scenes'][15]['ledger']['signal_applies']='RELEASED'
        s=summarize(compiled,result,snapshot)
        self.assertTrue(any(g['from_ordinal']==15 and g['to_ordinal']==15 for g in s['scene_groups']))

    def test_confirmed_scope_end_is_not_an_unresolved_condition(self):
        compiled,result,snapshot=self.fixture()
        ended={'condition_id':'crosswalk_ended','description':'이미 지나간 횡단보도','truth':'UNKNOWN','scope_state':'ENDED','evidence_refs':['f'],'evidence_note':'통과한 장면 확인'}
        snapshot['moments'][10]['components']['sequence_constraints']['payload']['constraints'].append(ended)
        compiled['scenes'][10]['constraints'].append(ended)
        s=summarize(compiled,result,snapshot)
        missing=[i for i in s['scenes'][10]['issues'] if i['code']=='EVIDENCE_MISSING']
        self.assertEqual(len(missing),1)
        self.assertEqual(missing[0]['sources'][0]['value']['condition_id'],'signal_applies')


    def test_same_exact_finding_has_one_card_and_property_link_but_distinct_inputs_survive(self):
        compiled,result,snapshot=self.fixture()
        source={'moment_id':'m10','component':'sequence_constraints','path':'/facts/10','value':{'atom':{'subject_ref':'e2','predicate':'APPLIES_TO','object_ref':'ego'},'truth':'FALSE','evidence_note':'영상만으로 확정하기 어렵다.'},'evidence_refs':['f']}
        snapshot['moments'][10]['components']['sequence_coc']['payload']['entities']=[{'entity_id':'ego','kind':'EGO','description':'자차'},{'entity_id':'e2','kind':'ZONE','description':'공사 구역'}]
        finding={'code':'UNSUPPORTED_ATOM','message':'원자 대상 종류 불일치','sources':[source]}
        row=result['scenes'][10];row['review_items']=[finding];row['properties']={'results':[{'property_id':'B1','status':'UNKNOWN','message':finding['message'],'checks':[finding],'sources':[source]}]}
        before=deepcopy((compiled,result,snapshot));point=summarize(compiled,result,snapshot)['scenes'][10]
        problems=[i for i in point['issues'] if i['code']=='UNSUPPORTED_ATOM'];self.assertEqual(len(problems),1)
        self.assertEqual(point['property_issue_ids']['B1'],[problems[0]['issue_id']]);self.assertEqual(problems[0]['property_ids'],['B1'])
        self.assertIn('잘못 연결',problems[0]['title']);self.assertIn('교통 표지',problems[0]['limitation']);self.assertIn('문제는 남',problems[0]['certainty_guidance'])
        self.assertEqual(problems[0]['sources'][0]['entity_labels']['e2'],'공사 구역')
        self.assertEqual((compiled,result,snapshot),before)
        distinct=deepcopy(finding);distinct['sources'][0]['path']='/facts/11';row['review_items'].append(distinct);row['properties']['results'][0]['checks'].append(distinct)
        self.assertEqual(len([i for i in summarize(compiled,result,snapshot)['scenes'][10]['issues'] if i['code']=='UNSUPPORTED_ATOM']),2)

    def test_previous_source_labels_and_property_only_failure_are_preserved(self):
        compiled,result,snapshot=self.fixture()
        prior=snapshot_moment(9,True,['CONTINUE']);prior['components']['sequence_coc']['payload']['entities']=[{'entity_id':'e2','kind':'ZONE','description':'이전 교차로'}];snapshot['moments'][9]=prior
        source={'moment_id':'m9','component':'sequence_coc','path':'/observed_actions/0','value':{'subject_ref':'ego','code':'HOLD','action_target_ref':'e2'}}
        result['scenes'][10]['properties']={'results':[{'property_id':'A4','status':'FAIL','message':'CAN과 불일치','checks':[],'sources':[source]}]}
        point=summarize(compiled,result,snapshot)['scenes'][10]
        self.assertEqual(point['display_status'],'CONTRADICTION')
        issue=next(i for i in point['issues'] if i['code']=='A4');self.assertEqual(issue['sources'][0]['entity_labels']['e2'],'이전 교차로')
        self.assertEqual(point['property_issue_ids']['A4'],[issue['issue_id']])


    def test_can_counterexample_suggests_only_the_failed_action_without_changing_input(self):
        compiled,result,snapshot=self.fixture();source={'moment_id':'m10','component':'sequence_coc','path':'/observed_actions/0','value':{'code':'HOLD','subject_ref':'ego','action_target_ref':None,'movement_ref':None,'evidence_refs':['CAN:0']}}
        finding={'code':'CAN_ACTION_CONTRADICTION','message':'CAN과 관찰 행동 충돌','sources':[source]}
        row=result['scenes'][10];row['review_items']=[finding];row['properties']={'results':[{'property_id':'A4','status':'FAIL','message':'행동·CAN 대조','sources':[source],'checks':[{'status':'FAIL','message':'8.3 km/h 측정과 정지 유지 행동을 대조했습니다.','speed_kmh':8.3}]}]}
        before=deepcopy((compiled,result,snapshot));point=summarize(compiled,result,snapshot)['scenes'][10];issue=next(i for i in point['issues'] if i['code']=='CAN_ACTION_CONTRADICTION')
        self.assertEqual(point['property_issue_ids']['A4'],[issue['issue_id']]);self.assertEqual(len(issue['suggestions']),1)
        candidate=issue['suggestions'][0];self.assertEqual((candidate['field'],candidate['before'],candidate['value']),('code','HOLD','CONTINUE'));self.assertEqual(candidate['kind'],'COUNTEREXAMPLE_CANDIDATE')
        self.assertIn('8.3',candidate['basis']);self.assertIn('보장하지',candidate['message']);self.assertEqual((compiled,result,snapshot),before)
        row['properties']['results'][0]['checks'][0]['status']='UNKNOWN'
        self.assertFalse(next(i for i in summarize(compiled,result,snapshot)['scenes'][10]['issues'] if i['code']=='CAN_ACTION_CONTRADICTION')['suggestions'])


    def test_evidence_note_provenance_and_previous_current_frames_are_read_only(self):
        compiled,result,snapshot=self.fixture();owner=snapshot['moments'][10]
        snapshot['moments'][9]['frame']={'frame_id':'f9','asset_id':'a9','ordinal':9,'timestamp_us':8550000}
        owner.update(revision=29,t0_us=9550000,frame={'frame_id':'f10','asset_id':'a10','ordinal':10,'timestamp_us':9550000})
        note='이전 영상의 GIVE WAY 표지가 현재 차로에 적용되는지는 확인하지 못했다.'
        value={'atom':{'predicate':'APPLIES_TO','subject_ref':'e2','object_ref':'ego'},'truth':'FALSE','evidence_refs':['f9','f10'],'evidence_note':note}
        payload=owner['components']['sequence_constraints']['payload'];payload.update(facts=[deepcopy(value)],original_candidate={'facts':[{**deepcopy(value),'truth':'UNKNOWN'}]},generation_job_id='generated-constraints')
        source={'moment_id':'m10','component':'sequence_constraints','path':'/facts/0','value':deepcopy(value),'evidence_refs':['f9','f10']}
        result['scenes'][10]['review_items']=[{'code':'UNSUPPORTED_ATOM','message':'대상 불일치','sources':[source]}]
        before=deepcopy((compiled,result,snapshot));projection=next(i for i in summarize(compiled,result,snapshot)['scenes'][10]['issues'] if i['code']=='UNSUPPORTED_ATOM')['sources'][0]
        self.assertEqual(projection['provenance']['input_revision'],29);self.assertEqual(projection['provenance']['generation_job_id'],'generated-constraints');self.assertEqual(projection['provenance']['note_origin'],'MODEL_ORIGINAL')
        self.assertEqual([(f['ordinal'],f['temporal_role']) for f in projection['linked_frames']],[(9,'PREVIOUS'),(10,'CURRENT')]);self.assertEqual((compiled,result,snapshot),before)
        source['value']['evidence_note']='사람이 수정한 다른 근거 문장'
        updated=next(i for i in summarize(compiled,result,snapshot)['scenes'][10]['issues'] if i['code']=='UNSUPPORTED_ATOM')['sources'][0]
        self.assertEqual(updated['provenance']['note_origin'],'REVIEWED_INPUT')
