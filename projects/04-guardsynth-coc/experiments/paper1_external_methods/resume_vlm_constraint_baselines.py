"""Resume interrupted evaluations and rerun unsaved fits with the frozen protocol."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import run_vlm_constraint_baselines as baseline
import run_vlm_generation_budget as generation


def evaluate_saved(run):
    import torch
    from peft import PeftModel
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    baseline.verify(run)
    folder = run/'temporal_semantic_no_rule_seed123'
    training = json.loads((folder/'training.json').read_text())
    assert training['updates'] == 180
    torch.manual_seed(123)
    processor = AutoProcessor.from_pretrained(baseline.MODELS['2b'], local_files_only=True)
    base = Qwen3VLForConditionalGeneration.from_pretrained(baseline.MODELS['2b'], local_files_only=True,
        dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
    model = PeftModel.from_pretrained(base, folder/'adapter')
    rows = baseline.load_rows(run, 'temporal_test')
    for mode, name in [('no_rule', 'predictions.jsonl'), ('rule', 'common_rule_predictions.jsonl')]:
        baseline.predict(model, processor, rows, mode, folder/name)
    baseline.write_json(folder/'COMPLETE.json', dict(task='temporal', arm='semantic_no_rule', seed=123,
        rows=len(rows), status='COMPLETE', evaluation_resumed_from_saved_adapter=True))


def evaluate_diagnostic(run):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    baseline.verify(run)
    folder = run/'generation_budget_diagnostic/2b_batch8'
    rows = baseline.load_rows(run, 'pretrained_test')
    path = folder/'predictions.jsonl'
    completed = baseline.common.read_rows(path)
    assert [r['id'] for r in completed] == [r['id'] for r in rows[:len(completed)]]
    assert len(completed) % 8 == 0
    processor = AutoProcessor.from_pretrained(baseline.MODELS['2b'], local_files_only=True)
    processor.tokenizer.padding_side = 'left'
    torch.manual_seed(0)
    model = Qwen3VLForConditionalGeneration.from_pretrained(baseline.MODELS['2b'], local_files_only=True,
        dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
    started = time.monotonic()
    with path.open('a') as stream:
        for offset in range(len(completed), len(rows), 8):
            batch = rows[offset:offset+8]
            outputs = baseline.common.generate_batch(model, processor, batch, [r['prompts']['rule'] for r in batch], 512)
            for case, output in zip(batch, outputs):
                choice = generation.parse_final(output['text'], case['labels'])
                strict = baseline.common.parse_answer(output['text'], case['labels'])
                record = {k:case[k] for k in ('id','task','encoding','duration_ms','pair_id','target')}
                record.update(response=output, prediction=choice, strict_prediction=strict,
                    strict_score=baseline.score(case, strict), **baseline.score(case, choice))
                stream.write(json.dumps(record)+'\n')
            stream.flush()
            print('2b batch8 resumed', min(offset+8,len(rows)), len(rows), flush=True)
    baseline.write_json(folder/'COMPLETE.json', dict(model='2b', rows=len(rows), batch_size=8,
        elapsed_seconds_resumed=time.monotonic()-started, resumed_at_row=len(completed),
        output_sha256=baseline.digest(path), gpu=torch.cuda.get_device_name(0)))


def finish(run):
    baseline.verify(run)
    record = dict(at=datetime.now(timezone.utc).isoformat(), controller_pid=os.getpid(),
        source_sha256=baseline.digest(Path(__file__)), reason='Previous execution sessions ended before completion',
        unchanged_protocol=True, saved_evaluation_rows=76, saved_diagnostic_rows=616,
        restarted_fits=['temporal_ce_rule_seed123','temporal_semantic_rule_seed123'])
    baseline.write_json(run/'execution_recovery.json', record)
    attempts = json.loads((run/'interrupted_attempts.json').read_text())
    for job in record['restarted_fits']:
        attempts.append(dict(job=job, last_progress=json.loads((run/job/'progress.json').read_text()),
            reason=record['reason']+'; restart from the same base and seed', predictions_excluded=True))
    baseline.write_json(run/'interrupted_attempts.json', attempts)
    def launch(index, action, gpu):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, OMP_NUM_THREADS='8', MKL_NUM_THREADS='8', TOKENIZERS_PARALLELISM='false')
        command = ['taskset','-c',f'{index*8}-{index*8+7}',sys.executable,str(Path(__file__)),action,'--run-id',run.name]
        with (run/f'recovery_{action}.log').open('w') as stream:
            return subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
    gpu7='GPU_ID_REMOVED'
    gpu9='GPU_ID_REMOVED'
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(launch,i,a,g) for i,(a,g) in enumerate([
            ('ce_rule',gpu7),('semantic_rule',gpu7),('saved',gpu9),('diagnostic',gpu9)])]
        codes=[j.result() for j in jobs]
    record.update(return_codes=codes, finished_at=datetime.now(timezone.utc).isoformat())
    baseline.write_json(run/'execution_recovery.json', record)
    assert codes == [0]*4, codes
    for name in ('hold-worker','temporal-worker'):
        path=run/(name+'.json')
        if path.exists(): path.rename(run/(name.replace('-','_')+'.json'))
    baseline.aggregate(run)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('finish','ce_rule','semantic_rule','saved','diagnostic'))
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    run=baseline.BASE/args.run_id
    if args.action=='finish': finish(run)
    elif args.action=='saved': evaluate_saved(run)
    elif args.action=='diagnostic': evaluate_diagnostic(run)
    else: baseline.fit(run,'temporal',args.action,123)
