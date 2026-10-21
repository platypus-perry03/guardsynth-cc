"""Resume interrupted batches without changing the frozen inference procedures."""
import argparse
import json
from pathlib import Path
import time

import run_reasoning_comparison as r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--family', choices=['temporal', 'static', 'maneuver'], required=True)
    args = parser.parse_args()
    root = r.OUTPUT / args.run_id
    folder = root / args.family
    assert not (folder / 'RESULT.json').exists(), 'Family already completed'
    manifest = json.loads((root / 'RUN_MANIFEST.json').read_text())
    for path, expected in manifest['sources'].items():
        assert r.digest(Path(path)) == expected, f'Frozen input changed: {path}'
    arm = manifest.get('input_arm', 'p0')
    cases = r.load_cases(args.family, arm=arm)
    unique = list(reversed(list({case['input_id']: case for case in reversed(cases)}.values())))
    states, pending = {}, []
    for seed in r.SEEDS:
        for method in r.TRIGGERS:
            path = folder / f'{method}-seed{seed}.jsonl'
            if path.exists():
                assert path.read_bytes().endswith(b'\n'), 'Incomplete JSONL line requires review'
            raw = r.read_rows(path) if path.exists() else []
            assert [x['input_id'] for x in raw] == [x['input_id'] for x in unique[:len(raw)]]
            assert len(raw) == len(unique) or len(raw) % 8 == 0, 'Interrupted partial batch requires review'
            for row, case in zip(raw, unique):
                assert row['model_first_text'] == r.first_text(case, method)
                if row['answer'] is not None:
                    assert row['model_second_text'] == r.second_text(case, method, row['reason']['text'])
            states[seed, method] = raw
            if len(raw) < len(unique):
                pending.append((seed, method, len(raw)))
    r.write_json(root / 'resume_manifest.json', {
        'reason': 'Unified execution process terminated during a turn interruption',
        'frozen_runner_sha256': r.digest(Path(r.__file__)),
        'resume_runner_sha256': r.digest(Path(__file__)),
        'family': args.family, 'pending': pending,
        'configuration': 'Same frozen checkpoint, prompts, extraction, greedy decoding, batch size 8 and token caps',
        'timing_scope': 'Per-record generation timings cover completed batches; interrupted unrecorded work is excluded',
    })
    started = time.perf_counter()
    setup_seconds = None
    if pending:
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        from peft import PeftModel
        processor = AutoProcessor.from_pretrained(r.MODEL, local_files_only=True)
        processor.tokenizer.padding_side = 'left'
        torch.manual_seed(0)
        base = Qwen3VLForConditionalGeneration.from_pretrained(
            r.MODEL, local_files_only=True, dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
        first_seed = pending[0][0]
        model = PeftModel.from_pretrained(base, r.learning(args.family) / f'{arm}-seed{first_seed}/adapter',
                                         adapter_name=f'seed{first_seed}')
        model.eval()
        loaded = {first_seed}
        setup_seconds = time.perf_counter() - started
        for seed, method, offset in pending:
            if seed not in loaded:
                model.load_adapter(r.learning(args.family) / f'{arm}-seed{seed}/adapter', adapter_name=f'seed{seed}')
                loaded.add(seed)
            model.set_adapter(f'seed{seed}')
            model.eval()
            with (folder / f'{method}-seed{seed}.jsonl').open('a') as stream:
                for start in range(offset, len(unique), 8):
                    batch = unique[start:start + 8]
                    first = r.generate_batch(model, processor, batch, [r.first_text(x, method) for x in batch], r.CAPS[method])
                    need = [i for i, x in enumerate(first) if method == 'zero_shot_cot' or r.ps_answer_tail(x['text']) is None]
                    second = r.generate_batch(model, processor, [batch[i] for i in need],
                                             [r.second_text(batch[i], method, first[i]['text']) for i in need], 32) if need else []
                    answers = dict(zip(need, second))
                    for i, (case, reason) in enumerate(zip(batch, first)):
                        final = answers.get(i)
                        tail = final['text'] if final is not None else r.ps_answer_tail(reason['text'])
                        row = dict(input_id=case['input_id'], image_sha256=case['image_sha256'],
                                   model_first_text=r.first_text(case, method),
                                   model_second_text=r.second_text(case, method, reason['text']) if final else None,
                                   reason=reason, answer=final, prediction=r.parse_answer(tail, case['labels']),
                                   generated_tokens=reason['tokens'] + (final['tokens'] if final else 0),
                                   generation_seconds=reason['seconds'] + (final['seconds'] if final else 0))
                        stream.write(json.dumps(row) + '\n')
                        states[seed, method].append(row)
                    stream.flush()
                    print(f'{args.family} seed{seed} {method}: {min(start + 8, len(unique))}/{len(unique)} resumed', flush=True)
    for (seed, method), raw in states.items():
        assert len(raw) == len(unique)
        records = {x['input_id']: x for x in raw}
        predictions = [dict(id=case['id'], task=case['task'], scene_id=case['scene_id'],
                            contract_level=case['contract_level'], target=case['target'], input_id=case['input_id'],
                            prediction=records[case['input_id']]['prediction'],
                            **r.score(case, records[case['input_id']]['prediction'])) for case in cases]
        path = folder / f'{method}-seed{seed}-predictions.jsonl'
        if path.exists():
            assert r.read_rows(path) == predictions, 'Existing predictions differ'
        else:
            path.write_text(''.join(json.dumps(x) + '\n' for x in predictions))
    r.write_json(folder / 'RESULT.json', {
        'status': 'COMPLETE', 'smoke': False, 'resumed': True,
        'scored_rows': len(cases) * len(r.SEEDS) * len(r.TRIGGERS), 'unique_inputs': len(unique),
        'model_setup_seconds': setup_seconds, 'worker_wall_seconds': None,
        'resume_worker_wall_seconds': time.perf_counter() - started,
        'timing_note': 'Previous interrupted worker wall time was not retained; completed batch timings remain in raw records',
    })


if __name__ == '__main__':
    main()
