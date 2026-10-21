from pathlib import Path
import sys,os,subprocess,json,csv,hashlib,random,platform,time
ROOT=Path('REPOSITORY_ROOT')
OUT=ROOT/'projects/04-guardsynth-coc/artifacts/intermediate/guardsynth-studio-sequential-coc-001/studio-verification-feasibility-test-2026-10-03-001'
OUT.mkdir(parents=True,exist_ok=False)
CAT={'sources':[{'id':'synthetic_rule','text':'Synthetic conditional test rule','locator':'synthetic fixture','reviewed':True,'expected_actions':['HOLD']}]}
def make_request(n,k,vary):
    rng=random.Random(20261003)
    moments=[]
    for i in range(n):
        if k<=16: ids=range(k)
        else: ids=range((i%4)*16,(i%4+1)*16)
        items=[]
        for j in ids:
            items.append({'condition_id':f'condition_{j}','scope_id':'synthetic_zone','description':f'Synthetic condition {j}',
                          'actions':['HOLD'],'effect':'REQUIRE','activation':'Condition observed','hold':'Until evidence of clearance',
                          'release':'Clearance observed','source_refs':['synthetic_rule'],
                          'truth':('TRUE' if rng.random()>.5 else 'FALSE') if vary else 'TRUE','scope_state':'IN_SCOPE',
                          'evidence_refs':[f'f{i}'],'evidence_note':'Synthetic fixture, not scene truth'})
        moments.append({'id':f'm{i}','ordinal':i,'t0_us':(i+1)*1000000,'frame_ids':[f'f{i}'],'reviewed':True,
                        'coc':{'observations':'Synthetic fixture','observed_actions':['HOLD'],'explanation':'Synthetic conditional test',
                               'unknowns':'','evidence_refs':[f'f{i}']},'constraints':{'constraints':items}})
    return {'moments':moments,'catalog':CAT}
cases=[('small_2x8',2,8,False),('typical_21x16',21,16,False),('dense_repeated_200x64',200,64,False),('dense_varying_200x64',200,64,True)]
inputs={c:make_request(n,k,v) for c,n,k,v in cases}
(OUT/'case_inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2)+'\n')
tracked=['projects/04-guardsynth-coc/src/guard_synth/studio_sequence.py','platforms/eblc-bcv/src/guard_synth_eblc/smt_compiler.py','apps/guardsynth_studio/jobs.py','apps/guardsynth_studio/task.py']
import z3
manifest={'project_id':'guardsynth-coc','subproject_id':'guardsynth-studio-sequential-coc','run_id':OUT.name,
          'experiment_id':'guardsynth-studio-sequential-coc-001','license_class':'intermediate',
          'purpose':'Current verifier performance probe only; seven-class causal redesign is not implemented or benchmarked',
          'synthetic_only':True,'paid_model_calls':0,'seed':20261003,'repeats':2,
          'task':'SEQ_CHECK','task_wall_limit_s':30,'task_cpu_limit_s':30,'task_address_space_limit_gib':1,
          'python':sys.version,'z3':z3.get_version_string(),'platform':platform.platform(),
          'logical_cpus':os.cpu_count(),'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tracked}}
(OUT/'RUN_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(OUT/'benchmark_probe.py').write_bytes(Path(__file__).read_bytes())
(OUT/'benchmark_measure.py').write_bytes(Path('/tmp/guardsynth_measure_verification.py').read_bytes())
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1',
     'PYTHONPATH':str(ROOT)+':'+str(ROOT/'projects/04-guardsynth-coc/src')+':'+str(ROOT/'platforms/eblc-bcv/src')}
rows=[]
for cid,n,k,v in cases:
    for rep in (1,2):
        payload={'case_id':cid,'repeat':rep,'request':inputs[cid]}
        p=subprocess.run([sys.executable,'-B','/tmp/guardsynth_measure_verification.py'],input=json.dumps(payload),text=True,capture_output=True,env=env,cwd=ROOT,timeout=40)
        if p.returncode: row={'case_id':cid,'repeat':rep,'execution':'MEASURE_FAILED','error':p.stderr[-400:]}
        else: row=json.loads(p.stdout)
        row.update(moment_count=n,max_condition_count=k,pattern='varying' if v else 'repeated')
        rows.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        (OUT/'RESULT.json').write_text(json.dumps({'status':'RUNNING','results':rows},ensure_ascii=False,indent=2)+'\n')
fields=sorted({k for r in rows for k in r})
with (OUT/'timing_results.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
result={'project_id':'guardsynth-coc','status':'COMPLETED_WITH_FINDINGS' if any(r['execution']!='COMPLETED' for r in rows) else 'COMPLETED',
        'paid_model_calls':0,'scope':'Synthetic current verifier only; not semantic or performance certification of the proposed design','results':rows}
(OUT/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('OUTPUT '+str(OUT),flush=True)
