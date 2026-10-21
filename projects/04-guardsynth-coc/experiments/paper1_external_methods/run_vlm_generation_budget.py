"""Post-hoc E1 output-budget sensitivity; preserves the frozen primary run."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import time

import run_vlm_constraint_baselines as baseline


def parse_final(text, labels):
    # Fixed before this diagnostic: final answer markers or a final sole-option
    # line take precedence over options discussed in an explanation.
    clean=text.strip().replace('**','')
    patterns=(r'(?:the\s+answer\s+is|final\s+answer|answer)\s*[:：]?\s*([A-D])\b',
              r'(?:^|\n)\s*([A-D])\s*[.]?\s*$')
    for pattern in patterns:
        matches=re.findall(pattern,clean,re.I)
        if matches:
            choice=matches[-1].upper()
            return choice if choice in labels else 'INVALID'
    return baseline.common.parse_answer(text,labels)


def evaluate(run,size):
    import torch
    from transformers import AutoProcessor,Qwen3VLForConditionalGeneration
    baseline.verify(run)
    root=run/'generation_budget_diagnostic'
    root.mkdir(exist_ok=True)
    protocol=root/'protocol.json'
    frozen=dict(project_id='guardsynth-coc',task_id='pretrained-generation-budget-sensitivity',
        reason='Primary 12-token run contained explanations truncated before a candidate label',
        design='Post-hoc diagnostic; report alongside primary, never replace it or select best scores',
        max_new_tokens=512,batch_size=2,decoding='Greedy; unchanged P2 prompts and images',
        parser='Last explicit answer marker, else final sole-option line, else original unique-option parser',
        models=['2b','8b'],source=baseline.digest(Path(__file__)),
        test_sha256=baseline.digest(run/'pretrained_test.jsonl'),
        created_at=datetime.now(timezone.utc).isoformat())
    if not protocol.exists(): baseline.write_json(protocol,frozen)
    else:
        existing=json.loads(protocol.read_text())
        for key in frozen:
            if key!='created_at': assert existing[key]==frozen[key],key
    folder=root/size
    folder.mkdir(exist_ok=True)
    if (folder/'COMPLETE.json').exists():
        print('Diagnostic already complete; preserved',size,flush=True)
        return
    processor=AutoProcessor.from_pretrained(baseline.MODELS[size],local_files_only=True)
    processor.tokenizer.padding_side='left'
    torch.manual_seed(0)
    model=Qwen3VLForConditionalGeneration.from_pretrained(baseline.MODELS[size],local_files_only=True,
        dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0')
    rows=baseline.load_rows(run,'pretrained_test')
    path=folder/'predictions.jsonl'
    completed=baseline.common.read_rows(path) if path.exists() else []
    assert [x['id'] for x in completed]==[x['id'] for x in rows[:len(completed)]]
    started=time.monotonic()
    with path.open('a') as stream:
        for offset in range(len(completed),len(rows),2):
            batch=rows[offset:offset+2]
            outputs=baseline.common.generate_batch(model,processor,batch,[x['prompts']['rule'] for x in batch],512)
            for case,output in zip(batch,outputs):
                prediction=parse_final(output['text'],case['labels'])
                strict=baseline.common.parse_answer(output['text'],case['labels'])
                record={k:case[k] for k in ('id','task','encoding','duration_ms','pair_id','target')}
                record.update(response=output,prediction=prediction,strict_prediction=strict,
                    strict_score=baseline.score(case,strict),**baseline.score(case,prediction))
                stream.write(json.dumps(record)+'\n')
            stream.flush()
            if offset%64==0 or offset+2>=len(rows): print(size,offset+len(batch),len(rows),flush=True)
    predictions=baseline.common.read_rows(path)
    groups=defaultdict(list)
    for case,row in zip(rows,predictions):
        assert row['id']==case['id']
        assert row['prediction']==parse_final(row['response']['text'],case['labels'])
        assert all(row[k]==v for k,v in baseline.score(case,row['prediction']).items())
        groups[row['task'],row['encoding']].append(row)
    summaries=[]
    for (task,encoding),group in groups.items():
        summaries.append(dict(task=task,encoding=encoding,**baseline.metrics(group),
            strict_accuracy=statistics.mean(x['strict_score']['correct'] for x in group),
            strict_invalid_rate=statistics.mean(not x['strict_score']['valid'] for x in group)))
    baseline.write_json(folder/'COMPLETE.json',dict(model=size,rows=len(predictions),
        elapsed_seconds=time.monotonic()-started,metrics=summaries,
        output_sha256=baseline.digest(path),gpu=torch.cuda.get_device_name(0)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--run-id',required=True)
    p.add_argument('--size',choices=('2b','8b'),required=True)
    args=p.parse_args()
    if not re.fullmatch(r'vlm-constraint-baselines-\d{4}-\d{2}-\d{2}-\d{3}',args.run_id): p.error('Invalid run ID')
    evaluate(baseline.BASE/args.run_id,args.size)
