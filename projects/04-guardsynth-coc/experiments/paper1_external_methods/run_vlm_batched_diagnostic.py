"""Complete the 2B output-budget diagnostic with an efficient inference batch.

The earlier batch-two partial output is retained but excluded from scores.
This changes execution batching, not prompts, weights, decoding or parsing.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import run_vlm_constraint_baselines as baseline
import run_vlm_generation_budget as generation


def evaluate(run):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    baseline.verify(run)
    folder=run/'generation_budget_diagnostic/2b_batch8'
    assert not folder.exists(), 'Refuse to overwrite a diagnostic'
    folder.mkdir(parents=True)
    partial=run/'generation_budget_diagnostic/2b/predictions.jsonl'
    baseline.write_json(folder/'protocol.json',dict(project_id='guardsynth-coc',
        task_id='pretrained-batched-generation-budget',created_at=datetime.now(timezone.utc).isoformat(),
        model='2b',batch_size=8,max_new_tokens=512,decoding='Greedy',
        prompts='Unchanged frozen P2 inputs; no demonstrations or training',
        parser='Same final-answer parser as the batch-two diagnostic',
        reason='Execution-batch amendment for throughput, before any full 2B diagnostic was available; not score-based selection',
        source_sha256=baseline.digest(Path(__file__)),
        parser_source_sha256=baseline.digest(Path(generation.__file__)),
        test_sha256=baseline.digest(run/'pretrained_test.jsonl'),
        excluded_partial=dict(path=str(partial.relative_to(baseline.ROOT)),
            sha256=baseline.digest(partial),rows=len(baseline.common.read_rows(partial)))))
    processor=AutoProcessor.from_pretrained(baseline.MODELS['2b'],local_files_only=True)
    processor.tokenizer.padding_side='left'
    torch.manual_seed(0)
    model=Qwen3VLForConditionalGeneration.from_pretrained(baseline.MODELS['2b'],local_files_only=True,
        dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0')
    rows=baseline.load_rows(run,'pretrained_test')
    path=folder/'predictions.jsonl';started=time.monotonic()
    with path.open('w') as stream:
        for offset in range(0,len(rows),8):
            batch=rows[offset:offset+8]
            outputs=baseline.common.generate_batch(model,processor,batch,[x['prompts']['rule'] for x in batch],512)
            for case,output in zip(batch,outputs):
                prediction=generation.parse_final(output['text'],case['labels'])
                strict=baseline.common.parse_answer(output['text'],case['labels'])
                record={k:case[k] for k in ('id','task','encoding','duration_ms','pair_id','target')}
                record.update(response=output,prediction=prediction,strict_prediction=strict,
                    strict_score=baseline.score(case,strict),**baseline.score(case,prediction))
                stream.write(json.dumps(record)+'\n')
            stream.flush()
            if offset%64==0 or offset+8>=len(rows):print('2b batch8',min(offset+8,len(rows)),len(rows),flush=True)
    baseline.write_json(folder/'COMPLETE.json',dict(model='2b',rows=len(rows),batch_size=8,
        elapsed_seconds=time.monotonic()-started,output_sha256=baseline.digest(path),
        gpu=torch.cuda.get_device_name(0)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);args=p.parse_args()
    if not re.fullmatch(r'vlm-constraint-baselines-\d{4}-\d{2}-\d{2}-\d{3}',args.run_id):p.error('Invalid run ID')
    evaluate(baseline.BASE/args.run_id)
