"""Replay saved paid VLM outputs through the maintained twelve-property path.

No provider calls or edits to original candidates. A controlled CAN label flip
is reported separately from actual generated errors.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import time

from guard_synth.studio_sequence import compile_sequence, verify_compiled, tool_signature


def load_pair(directory, fingerprints):
    moments=[]
    for point in (1,2):
        values=[]
        for suffix in ('coc_candidate','constraints_candidate','coc_request'):
            path=directory/f'revision_{point}_{suffix}.json';raw=path.read_bytes()
            fingerprints[str(path)]=hashlib.sha256(raw).hexdigest();values.append(json.loads(raw))
        coc,con,request=values;request=request['input_data'];now=request['frames'][-1]
        evidence=[f['frame_id'] for f in request['frames']];current=[now['frame_id']]
        for row in (request.get('vehicle_state') or {}).get('frames',[]):
            if row.get('sample'):
                ref='CAN:'+str(row['sample']['timestamp_us']);evidence.append(ref)
                if row['frame_timestamp_us']==now['timestamp_us']:current.append(ref)
        moments.append({'id':directory.name+'-'+str(point),'ordinal':point-1,'t0_us':now['timestamp_us'],
                        'reviewed':True,'frame_ids':evidence,'current_evidence_refs':current,
                        'coc':coc,'constraints':con,'vehicle_state':request.get('vehicle_state')})
    return moments


def run(source, output):
    output.mkdir(parents=True,exist_ok=False);fingerprints={};counts=defaultdict(Counter);rows=[];timings=[];core=Counter();controls=[]
    manifest={'project_id':'guardsynth-coc','run_id':output.name,'status':'RUNNING','paid_calls':0,
              'source':str(source),'tool_signature':tool_signature(),'scope':'Saved real outputs; immediately prior/current only; mutations counted separately.'}
    (output/'RUN_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for directory in sorted(source.glob('scene-*-pair-*')):
        moments=load_pair(directory,fingerprints);before=deepcopy(moments);start=time.perf_counter()
        compiled=compile_sequence(moments,{'sources':[]});verified=verify_compiled(compiled);elapsed=time.perf_counter()-start
        timings.append(elapsed);assert moments==before
        (output/(directory.name.replace('-','_')+'.json')).write_text(json.dumps({'moments':moments,'verification':verified},ensure_ascii=False,indent=2)+'\n')
        for row in verified['scenes']:
            core[row['status']]+=1
            for p in row['properties']['results']:
                counts[p['property_id']][p['status']]+=1
                rows.append({'pair':directory.name,'point':row['ordinal']+1,'property':p['property_id'],'category':p['category'],'status':p['status'],'detail':p['message']})
        if directory.name=='scene-0061-pair-005':
            flipped=deepcopy(moments);flipped[-1]['coc']['observed_actions'][0]['code']='HOLD'
            injected=verify_compiled(compile_sequence(flipped,{'sources':[]}))['scenes'][-1]
            original=verified['scenes'][-1]
            controls.append({'kind':'INJECTED_ACTION_LABEL_ONLY','source':directory.name,'original':original,'injected':injected,'restored':verify_compiled(compile_sequence(moments,{'sources':[]}))['scenes'][-1]})
            assert 'CAN_ACTION_CONTRADICTION' in injected['codes'] and 'CAN_ACTION_CONTRADICTION' not in original['codes']
    for path,expected in fingerprints.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected
    with (output/'property_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['pair','point','property','category','status','detail']);writer.writeheader();writer.writerows(rows)
    result={'project_id':'guardsynth-coc','status':'COMPLETE','pairs':len(timings),'points':sum(core.values()),'paid_calls':0,
            'core_status_counts':dict(core),'property_counts':{pid:dict(c) for pid,c in counts.items()},
            'pair_time_s':{'total':sum(timings),'max':max(timings),'mean':sum(timings)/len(timings)},
            'mutation_controls':len(controls),'unchanged_original_files':len(fingerprints),'tool_signature':tool_signature(),
            'claims':'Unknown and not-checked are not passes. Checklist omissions are not logical contradictions. No new generation or unbounded liveness evaluation.'}
    (output/'controls.json').write_text(json.dumps(controls,ensure_ascii=False,indent=2)+'\n')
    (output/'input_fingerprints.json').write_text(json.dumps(fingerprints,indent=2)+'\n')
    (output/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    manifest['status']='COMPLETE';(output/'RUN_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(run(args.source,args.output),ensure_ascii=False,indent=2))
