"""Saved real VLM pair -> isolated Studio EBLC/verification/CNL CPU jobs.

Harness approvals exercise the workflow; they are not human scene certification.
Provider remains disabled and original files are never edited.
"""
import argparse
import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from apps.guardsynth_studio.common import uid
from apps.guardsynth_studio.store import Store
from apps.guardsynth_studio.service import Service
from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio import sequence


def run(source, output):
    output.mkdir(parents=True,exist_ok=False);hashes={};payloads=[];requests=[]
    for point in (1,2):
        values=[]
        for suffix in ('coc_candidate','constraints_candidate','coc_request'):
            path=source/f'revision_{point}_{suffix}.json';raw=path.read_bytes()
            hashes[str(path)]=hashlib.sha256(raw).hexdigest();values.append(json.loads(raw))
        payloads.append(values[:2]);requests.append(values[2]['input_data'])
    manifest={'project_id':'guardsynth-coc','run_id':output.name,'status':'RUNNING','paid_calls':0,
              'source':str(source),'provider':'DISABLED','approvals':'TEST_HARNESS_ONLY','input_fingerprints':hashes}
    (output/'RUN_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    store=Store(output/'replay_store');service=Service(store)
    lineage=store.put('lineage',{'revision':0,'split':'train','confirmed':True})
    video=store.put('video',{'original_sha256':'f'*64,'asset_id':'replay_only','permission':True,
                            'source':'Saved real VLM output replay; no new generation','license':'restricted',
                            'revision':0,'lineage_group_id':lineage,'status':'READY','drive_id':'replay'})
    selected=list({f['timestamp_us']:f for f in requests[0]['frames']+requests[1]['frames']}.values())
    selected.sort(key=lambda f:f['timestamp_us'])
    frames=[{**f,'asset_id':uid(),'ordinal':i,'pts':f['timestamp_us'],'time_base':'1/1000000','dimensions':[640,360]} for i,f in enumerate(selected)]
    extraction=store.put('extraction',{'video_id':video,'frames':frames,'status':'READY','interval_s':0.5})
    with store.transaction():ids=[store.create_moment(extraction,i,f) for i,f in enumerate(frames)]
    measured={r['sample']['timestamp_us']:r['sample'] for req in requests for r in (req.get('vehicle_state') or {}).get('frames',[]) if r.get('sample')}
    state=requests[0].get('vehicle_state')
    if state and measured:
        value={k:state[k] for k in ('dataset','scene_id','source_sha256','clock_origin_utime')}
        value.update(schema_version=1,video_sha256='f'*64,transmission_approved=True,samples=[measured[t] for t in sorted(measured)])
        service.attach_vehicle_state(video,0,value,'test-harness',uid())
    authored=[ids[next(i for i,f in enumerate(frames) if f['timestamp_us']==req['frames'][-1]['timestamp_us'])] for req in requests]
    for mid,(coc,con) in zip(authored,payloads):
        for kind,value in (('sequence_coc',coc),('sequence_constraints',con)):
            with store.transaction():
                m=store.moment(mid);store.install(m,kind,{**deepcopy(value),'original_candidate':deepcopy(value),'accepted_unchanged':True,'origin':'SAVED_REAL_OUTPUT_REPLAY'})
                store.record_approval(m,kind,'APPROVE','test-harness');store.save(m,'test-harness')
    rows=[];jobs=[]
    for kind in ('SEQ_EBLC','SEQ_VERIFY','SEQ_CNL'):
        start=time.perf_counter();queued=sequence.enqueue_stage(service,extraction,kind,'test-harness',uid())
        Worker(service).run_once();job=store.get(queued['job_id'],'job');elapsed=time.perf_counter()-start
        rows.append({'stage':kind,'status':job['status'],'seconds':elapsed});jobs.append(job)
        (output/(kind.lower()+'.json')).write_text(json.dumps(job,ensure_ascii=False,indent=2)+'\n')
        assert job['status']=='SUCCEEDED',job.get('error')
    verified=jobs[1]['result'];assert all(len(r['properties']['results'])==12 for r in verified['scenes'])
    assert all('12개 속성' in r['text'] for r in jobs[2]['result']['samples'])
    for path,expected in hashes.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected
    with (output/'stage_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['stage','status','seconds']);writer.writeheader();writer.writerows(rows)
    result={'project_id':'guardsynth-coc','status':'COMPLETE','paid_calls':0,'stages':rows,'actual_generated_points':2,
            'empty_context_points':len(frames)-2,'verification_status':verified['status'],'originals_preserved':True,
            'approval_scope':'Harness approvals; not an actual human annotation decision.'}
    (output/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    manifest['status']='COMPLETE';(output/'RUN_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');store.close()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.source,args.output),ensure_ascii=False,indent=2))
