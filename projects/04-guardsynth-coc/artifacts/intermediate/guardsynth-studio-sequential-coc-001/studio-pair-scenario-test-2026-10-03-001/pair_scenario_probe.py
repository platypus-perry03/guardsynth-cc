from pathlib import Path
from copy import deepcopy
import argparse,json,csv,hashlib,time,resource,sys
import z3
from guard_synth_eblc.action_contract import parse_action_contract,lower_action_contract,var,literal,binary,conjunction
from guard_synth_eblc.core_ir import parse_core_model,declaration_map
from guard_synth_eblc.smt_compiler import compile_core_model,check_queries,_lower

ROOT=Path('REPOSITORY_ROOT')
DEFAULT=ROOT/'projects/04-guardsynth-coc/artifacts/intermediate/guardsynth-studio-sequential-coc-001/studio-pair-scenario-test-2026-10-03-001'
arg=argparse.ArgumentParser();arg.add_argument('--output',type=Path,default=DEFAULT);opts=arg.parse_args()
out=opts.output.resolve()
assert out.is_relative_to(ROOT/'projects/04-guardsynth-coc/artifacts/intermediate/guardsynth-studio-sequential-coc-001')
out.mkdir(parents=True,exist_ok=False)
resource.setrlimit(resource.RLIMIT_CPU,(10,10))
resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
REFS=['synthetic_policy_z1_m1','synthetic_scene_1','synthetic_scene_2']
COMMON_COC='자차는 적용 신호 S1이 적색이고 교차 차량 A가 충돌 영역에 있어, Z1 진입을 보류하며 정지 상태를 유지했다.'
BASE={
 'scope':{'subject':'ego','zone':'Z1','movement':'M1_straight','scene_count':2},
 'entities':[{'id':'ego','type':'VEHICLE'},{'id':'A','type':'VEHICLE'},{'id':'S1','type':'SIGNAL'},{'id':'Z1','type':'ZONE'},{'id':'M1_straight','type':'MOVEMENT'}],
 'relations':[{'subject':'S1','relation':'CONTROLS_MOVEMENT','object':'M1_straight','zone':'Z1'},
              {'subject':'A','relation':'CROSSES_PATH_OF','object':'ego','zone':'Z1','movement':'M1_straight'}],
 'condition_definitions':[
  {'condition_id':'signal_s1','class':'TRAFFIC_CONTROL','condition_target':'S1','action_subject':'ego','action':'ENTER','action_target':'Z1','movement':'M1_straight','effect':'FORBID','activation':'S1の適用信号が赤と確認','release':'同じS1の適用信号が緑と確認','rule_ref':'synthetic_policy_z1_m1'},
  {'condition_id':'cross_a','class':'VEHICLE','relation':'CROSSES_PATH_OF','condition_target':'A','action_subject':'ego','action':'ENTER','action_target':'Z1','movement':'M1_straight','effect':'FORBID','activation':'Aの当該衝突領域の占有を確認','release':'同じAの当該領域からの離脱を確認','rule_ref':'synthetic_policy_z1_m1'}],
 'previous_state_summary':{'signal_s1':'ACTIVE','cross_a':'ACTIVE'},
 'policy':{'id':'synthetic_policy_z1_m1','synthetic':True,'text':'Z1/M1에 진입하려면 선언된 신호 제한과 차량 A 제한의 해제를 확인해야 한다. 확인된 허용은 진입 의무가 아니다. 진입 보류는 정지 명령이 아니다.'},
 'temporal_assumptions':{'scene_1':{'precondition_observed_s':10.0,'decision_s':10.1,'post_observed_s':10.2},'scene_2':{'precondition_observed_s':11.0,'decision_s':11.1,'post_observed_s':11.2},'note':'가상 입력에서 조건이 행동 전 확인됐다고 명시함. 정량 동역학/실제 운전 인과 효과를 증명하지 않음.'}}
BASE['condition_definitions'][0].update(activation='자차 이동에 적용되는 S1의 적색 확인',release='같은 S1의 적용 신호가 녹색으로 바뀜을 확인')
BASE['condition_definitions'][1].update(activation='A의 해당 충돌 영역 점유 확인',release='같은 A의 해당 영역 이탈 확인')
SPECS=[
 ('s01_clear_and_enter','FALSE','ENTER_ZONE',True,['signal_s1','cross_a'],'PASS','녹색 신호와 차량 A의 충돌 영역 이탈을 확인하여, 자차는 Z1의 직진 경로로 진입했다.'),
 ('s02_active_and_enter','TRUE','ENTER_ZONE',True,['signal_s1','cross_a'],'FAIL','적용 신호가 녹색으로 바뀌어 자차는 Z1에 진입했다. 교차 차량 A는 여전히 해당 충돌 영역에 있다.'),
 ('s03_unknown_and_defer','UNKNOWN','DEFER_ENTRY',False,['signal_s1','cross_a'],'REVIEW_REQUIRED','적용 신호는 녹색이지만 차량 A가 가려져 이탈을 확인하지 못했다. 자차는 진입을 보류하며 정지 상태를 유지했다.'),
 ('s04_local_omission','TRUE','ENTER_ZONE',True,['signal_s1'],'FAIL','적용 신호가 녹색으로 바뀌어 자차는 Z1에 진입했다.'),
 ('s05_postcondition_mismatch','FALSE','ENTER_ZONE',False,['signal_s1','cross_a'],'FAIL','녹색 신호와 차량 A의 이탈을 확인하여 자차가 Z1에 진입을 완료했다고 CoC에 기록했다.')]

def make_contract(keep_cross=True):
    obligations=[{'obligation_id':'signal_s1','predicate_id':'red_signal_s1','target_entity_id':'S1','rule_ref':REFS[0],'source_refs':[REFS[0]]}]
    if keep_cross:obligations.append({'obligation_id':'cross_a','predicate_id':'cross_a_occupies_z1','target_entity_id':'A','rule_ref':REFS[0],'source_refs':[REFS[0]]})
    return {'contract_version':'eblc-action-contract-v0.1','contract_id':'pair_z1_m1','horizon':2,'claim_scope':'CONDITIONAL_ACTION_SELECTION_NOT_VEHICLE_SAFETY','subject_id':'ego','zone_id':'Z1','policy':'CLEAR_REQUIRED_FOR_ENTRY','source_refs':REFS,'obligations':obligations}

def make_core(case,keep_cross=True):
    contract=make_contract(keep_cross)
    core=lower_action_contract(parse_action_contract(contract))
    def clause(cid,formula,kind='ASSUMPTION',refs=None):
        core['clauses'].append({'id':cid,'kind':kind,'enforcement':'INITIAL','formula':formula,'source_refs':refs or REFS,'description':cid})
    for ob in contract['obligations']:
        oid=ob['obligation_id']
        clause(oid+'_before_pair_inactive',binary('eq',var(oid+'_prior_active'),literal(False)))
        for t in (0,1):
            truth='TRUE' if t==0 else ('FALSE' if oid=='signal_s1' else case['current_cross_truth'])
            valid=truth!='UNKNOWN'
            refs=[REFS[t+1]]
            clause(f'{oid}_fact_{t}',binary('eq',var(oid+'_truth',t),literal(truth,'Truth')),refs=refs)
            clause(f'{oid}_evidence_{t}',binary('eq',var(oid+'_evidence_valid',t),literal(valid)),refs=refs)
    core['declarations'].append({'name':'ego_inside_z1','sort':'BOOL','time_varying':True,'enum_name':None,'enum_values':[],'unit':None,'frame':None,'source_refs':REFS})
    clause('previous_location_outside',binary('eq',var('ego_inside_z1',0),literal(False)))
    clause('entry_completion_semantics',binary('eq',var('ego_inside_z1',1),{'op':'or','args':[var('ego_inside_z1',0),binary('eq',var('action',1),literal('ENTER_ZONE','Action'))]}),'LIFECYCLE')
    # The last case deliberately contradicts the entry-completion annotation with a synthetic observation.
    clause('current_location_observed',binary('eq',var('ego_inside_z1',1),literal(case['current_inside'])),refs=[REFS[2]])
    recorded=conjunction(binary('eq',var('action',0),literal('DEFER_ENTRY','Action')),binary('eq',var('action',1),literal(case['current_action'],'Action')))
    core['queries'].append({'id':'recorded_action','formula':recorded,'expected':'UNSAT' if case['expected_verdict']=='FAIL' and keep_cross else 'SAT','classification':'CONSISTENCY','source_refs':REFS,'description':'Compare the two scene action annotations with the conditional model.'})
    parse_core_model(core)
    return contract,core

def get_unsat_core(compiled):
    q=next(q for q in compiled.model.queries if q.query_id=='recorded_action')
    lower=_lower(q.formula,base_time=0,model=compiled.model,declarations=declaration_map(compiled.model),symbols=compiled.symbols,enum_codes=compiled.enum_codes)
    solver=z3.Solver();solver.set(timeout=1000)
    label_map={}
    for i,a in enumerate(compiled.assertions):
        label=f'a_{i}';label_map[label]=a.clause_id;solver.assert_and_track(a.expression,z3.Bool(label))
    solver.assert_and_track(lower.term,z3.Bool('recorded_action_query'))
    for c in lower.side_constraints:solver.add(c)
    status=solver.check()
    return sorted(set(label_map.get(str(x),str(x)) for x in solver.unsat_core())) if status==z3.unsat else []

rows=[];scene_rows=[];results=[]
for sid,truth,action,inside,local_ids,expected,coc in SPECS:
    case=deepcopy(BASE)
    case.update(case_id=sid,current_cross_truth=truth,current_action=action,current_inside=inside,current_local_constraint_ids=local_ids,expected_verdict=expected,
                scenes=[{'ordinal':1,'coc':COMMON_COC,'observations':{'signal':'RED','cross_a_occupancy':'TRUE','ego_position':'OUTSIDE_Z1'},'action_annotation':'HOLD','entry_decision':'DEFER_ENTRY','local_constraint_ids':['signal_s1','cross_a']},
                        {'ordinal':2,'coc':coc,'observations':{'signal':'GREEN','cross_a_occupancy':truth,'ego_position':'INSIDE_Z1' if inside else 'OUTSIDE_Z1'},'action_annotation':'ENTER' if action=='ENTER_ZONE' else 'HOLD','entry_decision':action,'local_constraint_ids':local_ids}])
    if sid=='s05_postcondition_mismatch':case['scenes'][1]['action_annotation_origin']='COC_CLAIM_CONTRADICTED_BY_POST_OBSERVATION'
    directory=out/sid;directory.mkdir()
    (directory/'scenario_input.json').write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n')
    start=time.perf_counter();contract,core=make_core(case)
    compiled=compile_core_model(parse_core_model(core));checked=check_queries(compiled)
    statuses={x['query_id']:x['status'] for x in checked['results']}
    verdict='FAIL' if statuses['recorded_action']=='UNSAT' else 'REVIEW_REQUIRED' if truth=='UNKNOWN' else 'PASS'
    assert statuses['base_consistency']=='SAT',(sid,statuses)
    assert verdict==expected,(sid,verdict,expected)
    missing_from_local=sorted(set(case['previous_state_summary'])-set(local_ids))
    emitted={ob['obligation_id'] for ob in contract['obligations']}
    missing_from_model=sorted(set(case['previous_state_summary'])-emitted)
    assert not missing_from_model
    diagnostic=get_unsat_core(compiled) if verdict=='FAIL' else []
    result={'case_id':sid,'verdict':verdict,'expected_verdict':expected,'base_consistency':statuses['base_consistency'],'recorded_action':statuses['recorded_action'],
            'scope':'Synthetic stated policy and fixed entity/zone/movement bindings; not scene safety or actual causal identification',
            'missing_from_local':missing_from_local,'missing_from_model':missing_from_model,'unsat_core_clause_ids':diagnostic,'model_horizon':core['horizon'],
            'variable_count':len(compiled.symbols),'source_frame_count':2}
    if sid=='s04_local_omission':
        _,naive=make_core(case,False);naive_result=check_queries(compile_core_model(parse_core_model(naive)))
        result['naive_without_carry']={'recorded_action':next(x['status'] for x in naive_result['results'] if x['query_id']=='recorded_action'),
                                      'missing_condition_ids':['cross_a'],'assessment':'INVALID_MODEL_MISSING_CARRY'}
        assert result['naive_without_carry']['recorded_action']=='SAT'
        (directory/'naive_core_without_carry.json').write_text(json.dumps(naive,ensure_ascii=False,indent=2)+'\n')
    result['elapsed_s']=round(time.perf_counter()-start,6)
    for filename,data in [('action_contract.json',contract),('core_model.json',core),('symbol_table.json',compiled.symbol_table),('source_map.json',compiled.source_map),('case_result.json',result)]:
        (directory/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    for query in checked['results']:
        (directory/(query['query_id']+'.smt2')).write_text(query.pop('smt2'))
    (directory/'smt_results.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2)+'\n')
    results.append(result)
    rows.append({k:result[k] for k in ['case_id','verdict','base_consistency','recorded_action','model_horizon','variable_count','elapsed_s']})
    for scene in case['scenes']:
        scene_rows.append({'case_id':sid,'scene':scene['ordinal'],'coc':scene['coc'],'signal':scene['observations']['signal'],'cross_a_occupancy':scene['observations']['cross_a_occupancy'],
                           'ego_position':scene['observations']['ego_position'],'action':scene['action_annotation'],'local_constraints':','.join(scene['local_constraint_ids']),
                           'inherited_conditions':'signal_s1,cross_a' if scene['ordinal']==2 else '', 'pair_verdict':verdict})
    print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
for filename,data in [('scenario_results.csv',rows),('scene_comparison.csv',scene_rows)]:
    with (out/filename).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
files=['platforms/eblc-bcv/src/guard_synth_eblc/action_contract.py','platforms/eblc-bcv/src/guard_synth_eblc/core_ir.py','platforms/eblc-bcv/src/guard_synth_eblc/smt_compiler.py','platforms/eblc-bcv/src/guard_synth_eblc/schemas/eblc_action_contract.schema.json','platforms/eblc-bcv/src/guard_synth_eblc/schemas/eblc_core_ir.schema.json']
manifest={'project_id':'guardsynth-coc','subproject_id':'guardsynth-studio-sequential-coc','experiment_id':'guardsynth-studio-sequential-coc-001','run_id':out.name,'license_class':'intermediate',
          'synthetic_only':True,'paid_model_calls':0,'scenario_count':len(results),'model_horizon':2,'engine':'Existing EBLC qualitative action lowering and Z3 Core compiler',
          'purpose':'Executable synthetic two-scene design examples; not full Studio implementation','z3':z3.get_version_string(),'python':sys.version,
          'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}}
(out/'RUN_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(out/'RESULT.json').write_text(json.dumps({'project_id':'guardsynth-coc','status':'COMPLETED_AS_EXPECTED','results':results,'paid_model_calls':0,'training_eligible':False,'scene_truth_certified':False},ensure_ascii=False,indent=2)+'\n')
(out/'pair_scenario_probe.py').write_bytes(Path(__file__).read_bytes())
print('OUTPUT '+str(out))
