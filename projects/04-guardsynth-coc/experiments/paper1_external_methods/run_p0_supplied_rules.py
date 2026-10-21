"""Evaluate existing CoC-only P0 adapters with frozen P1 rules at test time."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

import run_reasoning_comparison as r

METHODS = ('direct', 'zero_shot_cot', 'plan_and_solve')
FAMILIES = ('temporal', 'static', 'maneuver')
PRIOR = r.OUTPUT / 'constraint-reasoning-2026-10-07-001'
DEFAULT_RUN = 'seven-condition-reasoning-2026-10-07-001'


def model_text(case, method):
    return case['prompt'] if method == 'direct' else r.first_text(case, method)


def freeze(run_id):
    assert json.loads((PRIOR / 'RESULT.json').read_text())['status'] == 'COMPLETE'
    prior = json.loads((PRIOR / 'RUN_MANIFEST.json').read_text())
    files = {Path(p) for p in prior['sources']}
    files.add(Path(__file__).resolve())
    files.update(p for p in PRIOR.rglob('*') if p.is_file())
    for family in FAMILIES:
        for seed in r.SEEDS:
            files.update((r.learning(family) / f'p0-seed{seed}/adapter').glob('*'))
    folder = r.OUTPUT / run_id
    folder.mkdir(parents=True, exist_ok=False)
    r.write_json(folder / 'RUN_MANIFEST.json', dict(
        project_id='guardsynth-coc', run_id=run_id, frozen_at=datetime.now(timezone.utc).isoformat(),
        checkpoint_arm='p0', input_arm='p1', prior_run=str(PRIOR),
        methods=METHODS, seeds=r.SEEDS, dataset_audit=r.audit('p1'),
        planned_new_predictions=4320, additional_training=False, additional_human_labels=False,
        model_path=str(r.MODEL), sources={str(p): r.digest(p) for p in sorted(files) if p.is_file()},
        inference=dict(greedy=True, batch_size=8, dtype='bfloat16', attention='sdpa',
                       direct_max_new_tokens=12, reasoning_caps=r.CAPS, answer_max_new_tokens=32,
                       reasoning_instructions=r.TRIGGERS,
                       parser='Unique standalone uppercase option; missing/ambiguous/illegal answers INVALID',
                       deduplication='Identical image pixels and P1 prompt within each checkpoint and method'),
        protocol=dict(
            question='Separate rule-bearing training from inference-time rule provision and reasoning prompts',
            model_input='Exact frozen P1 image and user text, including natural-language rule and candidates',
            forbidden_input=['EBLC JSON', 'SMT verdicts', 'Reference labels', 'Hidden oracle metadata'],
            controls='P0 adapters trained on CoC-only rows receive rules only during evaluation',
            reused_conditions=['P1', 'P1 + ZS-CoT', 'P1 + PS', 'P2'],
            new_conditions=['P0 + rule', 'P0 + rule + ZS-CoT', 'P0 + rule + PS'],
            interpretation_limits=[
                'Same task rules at evaluation; training exposure to rules differs',
                'Existing synthetic data and independently trained checkpoints; no causal verification-effect isolation',
                'Native prompt procedures transferred to label-trained Qwen adapters; not original-paper reproductions',
                'Unequal native reasoning caps, truncated responses and label-only first stages reported explicitly',
                'Invalid responses are errors with unknown admissibility, not safe choices'])) )
    print(json.dumps(r.audit('p1')), flush=True)


def check_sources(root):
    manifest = json.loads((root / 'RUN_MANIFEST.json').read_text())
    assert manifest['checkpoint_arm'] == 'p0' and manifest['input_arm'] == 'p1'
    for path, expected in manifest['sources'].items():
        assert r.digest(Path(path)) == expected, f'Frozen source changed: {path}'
    return manifest


def evaluate(run_id, family):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from peft import PeftModel
    root = r.OUTPUT / run_id
    check_sources(root)
    folder = root / family
    assert not (folder / 'RESULT.json').exists(), 'Family already complete'
    folder.mkdir(exist_ok=True)
    cases = r.load_cases(family, arm='p1')
    unique = list(reversed(list({c['input_id']: c for c in reversed(cases)}.values())))
    states = {}
    for seed in r.SEEDS:
        for method in METHODS:
            path = folder / f'{method}-seed{seed}.jsonl'
            if path.exists():
                assert path.read_bytes().endswith(b'\n'), 'Partial JSONL line requires review'
            rows = r.read_rows(path) if path.exists() else []
            assert [x['input_id'] for x in rows] == [x['input_id'] for x in unique[:len(rows)]]
            assert len(rows) == len(unique) or len(rows) % 8 == 0
            for case, row in zip(unique, rows):
                assert row['model_first_text'] == model_text(case, method)
            states[seed, method] = rows
    processor = AutoProcessor.from_pretrained(r.MODEL, local_files_only=True)
    processor.tokenizer.padding_side = 'left'
    torch.manual_seed(0)
    started = time.perf_counter()
    base = Qwen3VLForConditionalGeneration.from_pretrained(
        r.MODEL, local_files_only=True, dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
    model = PeftModel.from_pretrained(base, r.learning(family) / 'p0-seed42/adapter', adapter_name='seed42')
    setup_seconds = time.perf_counter() - started
    resumed = sum(len(rows) for rows in states.values())
    for seed in r.SEEDS:
        if seed != 42:
            model.load_adapter(r.learning(family) / f'p0-seed{seed}/adapter', adapter_name=f'seed{seed}')
        model.set_adapter(f'seed{seed}')
        model.eval()
        for method in METHODS:
            rows = states[seed, method]
            with (folder / f'{method}-seed{seed}.jsonl').open('a') as stream:
                for offset in range(len(rows), len(unique), 8):
                    batch = unique[offset:offset + 8]
                    first = r.generate_batch(model, processor, batch, [model_text(c, method) for c in batch],
                                             12 if method == 'direct' else r.CAPS[method])
                    need = [] if method == 'direct' else [i for i, x in enumerate(first)
                        if method == 'zero_shot_cot' or r.ps_answer_tail(x['text']) is None]
                    second = r.generate_batch(model, processor, [batch[i] for i in need],
                        [r.second_text(batch[i], method, first[i]['text']) for i in need], 32) if need else []
                    answers = dict(zip(need, second))
                    for i, (case, reason) in enumerate(zip(batch, first)):
                        answer = answers.get(i)
                        tail = reason['text'] if method == 'direct' else (
                            answer['text'] if answer is not None else r.ps_answer_tail(reason['text']))
                        row = dict(input_id=case['input_id'], image_sha256=case['image_sha256'],
                            checkpoint_arm='p0', input_arm='p1',
                            model_first_text=model_text(case, method),
                            model_second_text=r.second_text(case, method, reason['text']) if answer else None,
                            reason=reason, answer=answer, prediction=r.parse_answer(tail, case['labels']),
                            generated_tokens=reason['tokens'] + (answer['tokens'] if answer else 0),
                            generation_seconds=reason['seconds'] + (answer['seconds'] if answer else 0))
                        rows.append(row)
                        stream.write(json.dumps(row) + '\n')
                    stream.flush()
                    print(f'{family} P0 seed{seed} {method}: {min(offset + 8, len(unique))}/{len(unique)}', flush=True)
            records = {x['input_id']: x for x in rows}
            predictions = [dict(id=c['id'], task=c['task'], scene_id=c['scene_id'], contract_level=c['contract_level'],
                input_id=c['input_id'], target=c['target'], prediction=records[c['input_id']]['prediction'],
                **r.score(c, records[c['input_id']]['prediction'])) for c in cases]
            path = folder / f'{method}-seed{seed}-predictions.jsonl'
            if path.exists():
                assert r.read_rows(path) == predictions
            else:
                path.write_text(''.join(json.dumps(x) + '\n' for x in predictions))
    r.write_json(folder / 'RESULT.json', dict(status='COMPLETE', scored_predictions=len(cases)*9,
        unique_inputs=len(unique), resumed_raw_records=resumed, model_setup_seconds=setup_seconds,
        current_worker_wall_seconds=time.perf_counter()-started, cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),
        gpu=torch.cuda.get_device_name(0), torch=torch.__version__,
        timing_scope='Recorded batch generation times exclude setup and any unsaved interrupted work'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'evaluate'])
    parser.add_argument('--run-id', default=DEFAULT_RUN)
    parser.add_argument('--family', choices=FAMILIES)
    args = parser.parse_args()
    if args.action == 'freeze':
        freeze(args.run_id)
    else:
        assert args.family
        evaluate(args.run_id, args.family)


if __name__ == '__main__':
    main()
