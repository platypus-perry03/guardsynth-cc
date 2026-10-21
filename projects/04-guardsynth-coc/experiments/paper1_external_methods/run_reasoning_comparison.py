"""Frozen inference controls; oracle metadata is used only for scoring."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
SOURCE = Path(__file__).resolve().parent
ART = Path('projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001')
OUTPUT = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-reasoning-comparison-001'
MODEL = Path.home() / '.cache/huggingface/hub/models--Qwen--Qwen3-VL-2B-Instruct/snapshots/89644892e4d85e24eaac8bacfd4f463576704203'
SEEDS = (42, 17, 123)
TRIGGERS = {
    'zero_shot_cot': "Let's think step by step.",
    'plan_and_solve': "Let's first understand the problem and devise a plan to solve the problem. Then, let's carry out the plan to solve the problem step by step.",
}
CAPS = {'zero_shot_cot': 128, 'plan_and_solve': 256}


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def package(family):
    if family == 'temporal':
        return ROOT / ART / 'temporal-training-data-2026-09-29-001'
    return ROOT / ART / f'{family}-contract-protocol-2026-09-30-003'


def learning(family):
    if family == 'temporal':
        return ROOT / ART / 'temporal-expansion-learning-2026-09-29-001'
    return ROOT / ART / f'{family}-contract-learning-2026-09-30-001'


def worlds():
    folder = ROOT / 'projects/01-safety-constrained-coc/experiments/vlm_guard_learning'
    sys.path.insert(0, str(folder))
    return importlib.import_module('candidate_guard_world'), importlib.import_module('maneuver_guard_world')


def load_cases(family, split='test', arm='p0'):
    from PIL import Image
    cases = []
    folder = package(family)
    assert arm in ('p0', 'p1', 'p2')
    frozen = read_rows(folder / f'{split}_{arm}.jsonl')
    if family == 'temporal':
        metadata = {row['id']: row for row in read_rows(folder / f'{split}_paired.jsonl')}
    else:
        cw, mw = worlds()
    for row in frozen:
        if family == 'temporal':
            meta = metadata[row['id']]
            image = Image.open(folder / row['image']).convert('RGB')
            expected = row['image_pixel_sha256']
            task = 'temporal'
            scene_id = meta['scene']['scene_id']
            target = meta['reference_action']
        elif family == 'static':
            meta = row['example']
            data = meta['scene']
            scene = cw.CandidateScene(data['scene_id'], data['visual_seed'], cw.Candidate(**data['candidate_a']), cw.Candidate(**data['candidate_b']))
            image = cw.render_candidate_scene(scene)
            expected = row['image_sha256']
            task, scene_id, target = meta['constraint_kind'], scene.scene_id, meta['target']
        else:
            meta = row['example']
            data = meta['scene']
            scene = mw.ManeuverScene(data['scene_id'], data['maneuver'], data['visual_seed'], tuple(mw.ManeuverCandidate(**x) for x in data['candidates']))
            image = mw.render_scene(scene)
            expected = row['image_sha256']
            task, scene_id, target = scene.maneuver, scene.scene_id, meta['target']
        actual = hashlib.sha256(image.tobytes()).hexdigest()
        assert actual == expected, (family, row['id'], 'image mismatch')
        # Identity uses image pixels and the supplied arm's text, never oracle metadata.
        identity = hashlib.sha256((actual + '\n' + row['prompt']).encode()).hexdigest()
        cases.append(dict(id=row['id'], family=family, task=task, scene_id=scene_id,
                          contract_level=meta['contract_level'], target=target, meta=meta,
                          image=image, image_sha256=actual, prompt=row['prompt'], input_id=identity,
                          labels='AB' if family == 'static' else 'ABCD'))
    return cases


def allowed_candidates(case):
    meta, family = case['meta'], case['family']
    if family == 'temporal':
        release = round(meta['scene']['clear_time'] * 1000) + meta['required_clear_ms']
        candidates = meta['scene']['candidates']
        return {x['label']: (x['entry_time'] is None or round(x['entry_time'] * 1000) >= release, x['progress']) for x in candidates}
    if family == 'static':
        cw, _ = worlds()
        return {x['name']: (cw.satisfies(cw.Candidate(**x), meta['constraint_kind'], meta['threshold']), x['progress']) for x in (meta['scene']['candidate_a'], meta['scene']['candidate_b'])}
    _, mw = worlds()
    scene_data = meta['scene']
    scene = mw.ManeuverScene(scene_data['scene_id'], scene_data['maneuver'], scene_data['visual_seed'], tuple(mw.ManeuverCandidate(**x) for x in scene_data['candidates']))
    example = mw.ManeuverExample(scene=scene, **{k: v for k, v in meta.items() if k != 'scene'})
    return {x.label: (mw.admissible(x, example), x.progress) for x in scene.candidates}


def parse_answer(text, labels):
    # Dataset adapter: accept only an unambiguous stand-alone option, never letters in words.
    for marker in ('The answer is', 'Therefore, the answer is', 'Therefore,the answer is', 'the answer is'):
        if marker in text:
            text = text.rsplit(marker, 1)[-1]
            break
    found = re.findall(r'(?<![A-Za-z])([A-E])(?![A-Za-z])', text)
    unique = set(found)
    return found[0] if len(unique) == 1 and found[0] in labels else 'INVALID'


def ps_answer_tail(reason):
    if 'The answer is' in reason:
        return reason.rsplit('The answer is', 1)[-1]
    if 'Therefore, the answer is' in reason:
        return reason.rsplit('the answer is', 1)[-1]
    return None


def first_text(case, method):
    separator = 'Q: ' if method == 'zero_shot_cot' else 'Q:'
    return separator + case['prompt'] + '\nA: ' + TRIGGERS[method]


def second_text(case, method, reason):
    trigger = ('\nTherefore, among A through D, the answer is' if case['labels'] == 'ABCD' else '\nTherefore, among A and B, the answer is') if method == 'zero_shot_cot' else 'Therefore,the answer is'
    return first_text(case, method) + reason + ' ' + trigger


def score(case, prediction):
    allowed = allowed_candidates(case)
    reference = max((label for label, (ok, _) in allowed.items() if ok), key=lambda x: allowed[x][1])
    assert reference == case['target'], (case['id'], reference, case['target'])
    valid = prediction in allowed
    return dict(valid=valid, correct=prediction == reference,
                violation=(not allowed[prediction][0]) if valid else None)


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['task'], row['scene_id'])].append(row)
    assert all(len(pair) == 2 for pair in groups.values())
    n = len(rows)
    valid_count = sum(row['valid'] for row in rows)
    violations = sum(row['violation'] is True for row in rows)
    return dict(rows=n, pairs=len(groups), accuracy=sum(row['correct'] for row in rows) / n,
                violation_rate=violations / n, violation_rate_valid_only=violations / valid_count if valid_count else None,
                invalid_rate=1 - valid_count / n,
                pair_accuracy=sum(all(row['correct'] for row in pair) for pair in groups.values()) / len(groups))


def audit(arm='p0'):
    report = {}
    for family in ('temporal', 'static', 'maneuver'):
        cases = load_cases(family, arm=arm)
        groups = defaultdict(list)
        for case in cases:
            score(case, case['target'])
            groups[case['input_id']].append(case)
        maximum = sum(max(Counter(x['target'] for x in group).values()) for group in groups.values()) / len(cases)
        report[family] = dict(rows=len(cases), unique_inputs=len(groups), fixed_input_accuracy_ceiling=maximum)
    return report


def freeze(run_id, arm='p0'):
    folder = OUTPUT / run_id
    folder.mkdir(parents=True, exist_ok=False)
    protocol_path = SOURCE / ('constraint_reasoning_protocol_v0_1.json' if arm == 'p1' else 'reasoning_comparison_protocol_v0_1.json')
    protocol = json.loads(protocol_path.read_text())
    files = [Path(__file__), protocol_path]
    for family in ('temporal', 'static', 'maneuver'):
        files.extend(package(family) / f'test_{name}.jsonl' for name in ('p0', 'p1', 'p2'))
        files.append(package(family) / ('test_paired.jsonl' if family == 'temporal' else 'test_contracts.jsonl'))
        for seed in SEEDS:
            files.extend((learning(family) / f'{arm}-seed{seed}/adapter').glob('*'))
            for baseline in ('p0', 'p1', 'p2'):
                files.append(learning(family) / f'{baseline}-seed{seed}/test.jsonl')
    files.extend(Path(x.__file__) for x in worlds())
    manifest = dict(project_id='guardsynth-coc', run_id=run_id, frozen_at=datetime.now(timezone.utc).isoformat(),
                    protocol=protocol, input_arm=arm, dataset_audit=audit(arm), model_path=str(MODEL),
                    sources={str(p): digest(p) for p in files if p.is_file()},
                    inference=dict(greedy=True, batch_size=8, dtype='bfloat16', attention='sdpa',
                                   prompts=TRIGGERS, reasoning_caps=CAPS, answer_cap=32,
                                   cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES', 'all'),
                                   ps_final_trigger='Therefore,the answer is',
                                   ps_extraction='Native conditional extraction on original exact answer markers',
                                   choice_parser='Unique standalone uppercase A-E in answer tail; illegal/ambiguous/missing options INVALID',
                                   multimodal_transfer='Original completion text in a Qwen user turn with the existing image; no few-shot examples',
                                   deduplication=f'One greedy generation per identical pixel hash and {arm.upper()} prompt, per method and checkpoint; copied predictions scored under every paired rule',
                                   timing='Batch generation wall time divided by batch size; report unique generations and total GPU worker wall time separately',
                                   extra_training=False),
                    claim=f'Prompting-strategy transfer on existing {arm.upper()} LoRA checkpoints; no original-paper model reproduction; unequal token caps')
    write_json(folder / 'RUN_MANIFEST.json', manifest)
    print(json.dumps(manifest['dataset_audit']), flush=True)


def generate_batch(model, processor, cases, texts, cap):
    import torch
    messages = [[dict(role='user', content=[dict(type='image', image=case['image']), dict(type='text', text=text)])] for case, text in zip(cases, texts)]
    encoded = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                           return_dict=True, return_tensors='pt', padding=True)
    encoded = {k: v.to('cuda:0') if hasattr(v, 'to') else v for k, v in encoded.items()}
    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**encoded, do_sample=False, max_new_tokens=cap, use_cache=True,
                                pad_token_id=processor.tokenizer.pad_token_id)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    generated = output[:, encoded['input_ids'].shape[1]:]
    raw = processor.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    special = set(processor.tokenizer.all_special_ids)
    result = []
    for text, ids in zip(raw, generated.tolist()):
        count = sum(i not in special for i in ids)
        result.append(dict(text=text.strip(), tokens=count, seconds=elapsed / len(cases), hit_token_cap=len(ids) == cap and ids[-1] not in special))
    return result


def evaluate_family(run_id, family, smoke=False):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from peft import PeftModel
    folder = OUTPUT / run_id / (family + ('-smoke' if smoke else ''))
    folder.mkdir(exist_ok=False)
    manifest = json.loads((OUTPUT / run_id / 'RUN_MANIFEST.json').read_text())
    assert digest(Path(__file__)) == manifest['sources'][str(Path(__file__))], 'Frozen runner changed'
    arm = manifest.get('input_arm', 'p0')
    for path, expected in manifest['sources'].items():
        assert digest(Path(path)) == expected, f'Frozen input changed: {path}'
    cases = load_cases(family, 'train' if smoke else 'test', arm=arm)
    unique = {case['input_id']: case for case in reversed(cases)}
    unique = list(reversed(list(unique.values())))
    if smoke:
        unique = unique[:2]
        ids = {x['input_id'] for x in unique}
        cases = [x for x in cases if x['input_id'] in ids]
    processor = AutoProcessor.from_pretrained(MODEL, local_files_only=True)
    processor.tokenizer.padding_side = 'left'
    torch.manual_seed(0)
    started = time.perf_counter()
    base = Qwen3VLForConditionalGeneration.from_pretrained(MODEL, local_files_only=True, dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
    model = PeftModel.from_pretrained(base, learning(family) / f'{arm}-seed42/adapter', adapter_name='seed42')
    model.eval()
    setup_seconds = time.perf_counter() - started
    seeds = (42,) if smoke else SEEDS
    for seed in seeds:
        name = f'seed{seed}'
        if seed != 42:
            model.load_adapter(learning(family) / f'{arm}-seed{seed}/adapter', adapter_name=name)
        model.set_adapter(name)
        model.eval()
        for method in TRIGGERS:
            records = {}
            stream_path = folder / f'{method}-seed{seed}.jsonl'
            with stream_path.open('x') as stream:
                for offset in range(0, len(unique), 8):
                    batch = unique[offset:offset + 8]
                    first = generate_batch(model, processor, batch, [first_text(x, method) for x in batch], CAPS[method])
                    need = [i for i, x in enumerate(first) if method == 'zero_shot_cot' or ps_answer_tail(x['text']) is None]
                    second = generate_batch(model, processor, [batch[i] for i in need], [second_text(batch[i], method, first[i]['text']) for i in need], 32) if need else []
                    answers = dict(zip(need, second))
                    for i, (case, reason) in enumerate(zip(batch, first)):
                        final = answers.get(i)
                        tail = final['text'] if final is not None else ps_answer_tail(reason['text'])
                        prediction = parse_answer(tail, case['labels'])
                        record = dict(input_id=case['input_id'], image_sha256=case['image_sha256'],
                                      model_first_text=first_text(case, method),
                                      model_second_text=second_text(case, method, reason['text']) if final else None,
                                      reason=reason, answer=final, prediction=prediction,
                                      generated_tokens=reason['tokens'] + (final['tokens'] if final else 0),
                                      generation_seconds=reason['seconds'] + (final['seconds'] if final else 0))
                        records[case['input_id']] = record
                        stream.write(json.dumps(record) + '\n')
                    stream.flush()
                    print(f'{family} seed{seed} {method}: {min(offset+8,len(unique))}/{len(unique)} unique inputs', flush=True)
            predictions = []
            for case in cases:
                prediction = records[case['input_id']]['prediction']
                predictions.append(dict(id=case['id'], task=case['task'], scene_id=case['scene_id'],
                                        contract_level=case['contract_level'], target=case['target'],
                                        input_id=case['input_id'], prediction=prediction, **score(case, prediction)))
            (folder / f'{method}-seed{seed}-predictions.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in predictions))
    write_json(folder / 'RESULT.json', dict(status='COMPLETE', smoke=smoke, scored_rows=len(cases)*len(seeds)*2,
                                         unique_inputs=len(unique), model_setup_seconds=setup_seconds,
                                         worker_wall_seconds=time.perf_counter()-started,
                                         gpu=torch.cuda.get_device_name(0), torch=torch.__version__))


def aggregate(run_id):
    folder = OUTPUT / run_id
    summary = defaultdict(lambda: defaultdict(list))
    costs = defaultdict(lambda: defaultdict(list))
    scored = 0
    for family in ('temporal', 'static', 'maneuver'):
        assert json.loads((folder / family / 'RESULT.json').read_text())['status'] == 'COMPLETE'
        for seed in SEEDS:
            for method in TRIGGERS:
                rows = read_rows(folder / family / f'{method}-seed{seed}-predictions.jsonl')
                assert len(rows) == {'temporal':240,'static':144,'maneuver':96}[family]
                scored += len(rows)
                for task in sorted({x['task'] for x in rows}):
                    summary[task][method].append(dict(seed=seed, **summarize([x for x in rows if x['task']==task])))
                raw = read_rows(folder / family / f'{method}-seed{seed}.jsonl')
                costs[family][method].append(dict(seed=seed, unique_inputs=len(raw),
                    mean_generated_tokens=statistics.mean(x['generated_tokens'] for x in raw),
                    total_generated_tokens=sum(x['generated_tokens'] for x in raw),
                    generation_seconds=sum(x['generation_seconds'] for x in raw),
                    reason_cap_hits=sum(x['reason']['hit_token_cap'] for x in raw),
                    reason_label_only=sum(parse_answer(x['reason']['text'], 'AB' if family=='static' else 'ABCD')!='INVALID' and len(x['reason']['text']) < 8 for x in raw)))
            for arm in ('p0', 'p1', 'p2'):
                archived = read_rows(learning(family) / f'{arm}-seed{seed}/test.jsonl')
                rows = [dict(task=x.get('subtype','temporal'), scene_id=x['scene_id'],
                             correct=x['correct'], valid=x['valid'],
                             violation=x.get('violation',x.get('guard_violation'))) for x in archived]
                for task in sorted({x['task'] for x in rows}):
                    summary[task][arm.upper()].append(dict(seed=seed, **summarize([x for x in rows if x['task']==task])))
    assert scored == 2880
    means = {task: {method: {metric: statistics.mean(x[metric] for x in seeds) for metric in ('accuracy','violation_rate','pair_accuracy','invalid_rate')} for method,seeds in methods.items()} for task,methods in summary.items()}
    write_json(folder / 'RESULT.json', dict(status='COMPLETE', project_id='guardsynth-coc', scored_predictions=scored,
        input_arm=json.loads((folder/'RUN_MANIFEST.json').read_text()).get('input_arm', 'p0'),
        unique_inference_costs=costs, three_seed_means=means, per_seed=summary,
        caveats=json.loads((folder/'RUN_MANIFEST.json').read_text())['protocol']['interpretation_limits']))
    print(json.dumps(means, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['audit','freeze','smoke','evaluate','aggregate'])
    p.add_argument('--run-id', default='reasoning-comparison-2026-10-07-001')
    p.add_argument('--family', choices=['temporal','static','maneuver'])
    p.add_argument('--arm', choices=['p0', 'p1'], default='p0')
    args = p.parse_args()
    if args.action == 'audit': print(json.dumps(audit(args.arm), indent=2))
    elif args.action == 'freeze': freeze(args.run_id, args.arm)
    elif args.action == 'aggregate': aggregate(args.run_id)
    else: evaluate_family(args.run_id, args.family, args.action == 'smoke')


if __name__ == '__main__':
    main()
