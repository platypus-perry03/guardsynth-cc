"""Frozen pretrained-VLM and categorical semantic-loss comparisons.

Owner: guardsynth-coc. Reuses archived inputs, not newly labeled scenes.
Run prepare before executing any fit or pretrained inference.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

import run_reasoning_comparison as common
import run_position_hold_selection as hold
import train_position_hold_selection as hold_training

ROOT = common.ROOT
SOURCE = Path(__file__).resolve().parent
PROTOCOL = SOURCE / 'vlm_constraint_baselines_protocol_v0_1.json'
BASE = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-vlm-constraint-baselines-001'
MODEL8 = ROOT / 'runtime/alpamayo/hf_cache/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b'
MODELS = {'2b': common.MODEL, '8b': MODEL8}
LABELS = 'ABCD'


def write_json(path, value):
    common.write_json(path, value)


def digest(path):
    return common.digest(path)


def rules(case):
    """Admissibility is independent of the reference label and model output."""
    if case['family'] == 'position_hold':
        row = case['meta']
        return {c['label']: (hold.maximum_squared_mm(c, row['hold_ms']) <= 40000,
                             c['progress']) for c in row['candidates']}
    return common.allowed_candidates(case)


def score(case, prediction):
    allowed = rules(case)
    reference = max((x for x in allowed if allowed[x][0]), key=lambda x: allowed[x][1])
    assert reference == case['target'], case['id']
    valid = prediction in allowed
    return dict(valid=valid, correct=prediction == reference,
                violation=not allowed[prediction][0] if valid else None)


def legacy_cases(family, split):
    with_rule = common.load_cases(family, split, 'p2')
    def identity(row):
        return json.dumps(row['id'], separators=(',', ':'))
    without_rule = {identity(x): x for x in common.load_cases(family, split, 'p0')}
    image_paths = {x['id']: x['image'] for x in common.read_rows(common.package(family) / f'{split}_p2.jsonl')} if family == 'temporal' else {}
    result = []
    for c in with_rule:
        p0 = without_rule[identity(c)]
        assert c['image_sha256'] == p0['image_sha256'] and c['target'] == p0['target']
        c['source_id'] = c['id']
        c['id'] = family + ':' + (c['id'] if isinstance(c['id'], str) else identity(c))
        c['prompts'] = {'rule': c.pop('prompt'), 'no_rule': p0['prompt']}
        c.pop('image')
        c.pop('input_id')
        c['encoding'] = 'candidate_scalars'
        c['pair_id'] = f"{family}:{c['task']}:{c['scene_id']}"
        c['duration_ms'] = c['meta'].get('required_clear_ms')
        if family == 'temporal':
            c['image_path'] = str((common.package(family) / image_paths[c['source_id']]).relative_to(ROOT))
        result.append(c)
    return result


def hold_cases(split):
    from PIL import Image
    result = []
    for row in common.read_rows(hold_training.RUN / f'{split}.jsonl'):
        image = Image.open(hold_training.RUN / row['image']).convert('RGB')
        assert row['target'] == hold.reference(row)
        assert row['prompts'] == {a: hold_training.prompt(row, a) for a in ('p0', 'p1', 'p2')}
        result.append(dict(id='position_hold:' + row['id'], source_id=row['id'],
            family='position_hold', task='position_hold', meta=row, target=row['target'],
            labels='ABCD', encoding=row['encoding'], duration_ms=row['hold_ms'],
            pair_id='position_hold:' + row['id'].rsplit('-', 2)[0] + ':' + row['encoding'],
            image_path=str((hold_training.RUN / row['image']).relative_to(ROOT)),
            image_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
            prompts={'rule': row['prompts']['p2'], 'no_rule': row['prompts']['p0']}))
    return result


def load_image(case):
    from PIL import Image
    if 'image_path' in case:
        image = Image.open(ROOT / case['image_path']).convert('RGB')
    else:
        cw, mw = common.worlds()
        scene = case['meta']['scene']
        if case['family'] == 'static':
            image = cw.render_candidate_scene(cw.CandidateScene(scene['scene_id'], scene['visual_seed'],
                cw.Candidate(**scene['candidate_a']), cw.Candidate(**scene['candidate_b'])))
        else:
            image = mw.render_scene(mw.ManeuverScene(scene['scene_id'], scene['maneuver'], scene['visual_seed'],
                tuple(mw.ManeuverCandidate(**x) for x in scene['candidates'])))
    assert hashlib.sha256(image.tobytes()).hexdigest() == case['image_sha256'], case['id']
    return image


def input_audit(rows, mode):
    grouped = defaultdict(list)
    for row in rows:
        identity = row['image_sha256'] + '\n' + row['prompts'][mode]
        grouped[identity].append(row['target'])
    return dict(rows=len(rows), unique_inputs=len(grouped),
        deterministic_accuracy_ceiling=sum(max(Counter(v).values()) for v in grouped.values()) / len(rows))


def prepare(run):
    assert not run.exists(), 'Refuse to overwrite a run'
    protocol = json.loads(PROTOCOL.read_text())
    data = {}
    for task in ('temporal', 'position_hold'):
        data[task + '_train'] = legacy_cases(task, 'train') if task == 'temporal' else hold_cases('train')
        data[task + '_test'] = legacy_cases(task, 'test') if task == 'temporal' else hold_cases('test')
        assert len(data[task + '_train']) == 960
    data['pretrained_test'] = (data['temporal_test'] + legacy_cases('static', 'test')
                               + legacy_cases('maneuver', 'test') + data['position_hold_test'])
    assert len(data['pretrained_test']) == protocol['e1']['rows']
    for rows in data.values():
        assert len({x['id'] for x in rows}) == len(rows)
        for row in rows:
            allowed = rules(row)
            row['allowed_labels'] = [x for x in row['labels'] if allowed[x][0]]
            assert row['allowed_labels'] and score(row, row['target'])['correct']
        pairs = Counter(x['pair_id'] for x in rows)
        assert set(pairs.values()) == {2}
    sources = [Path(__file__), PROTOCOL, Path(common.__file__), Path(hold.__file__),
               Path(hold_training.__file__),
               ROOT / 'projects/01-safety-constrained-coc/experiments/vlm_guard_learning/train_qwen_temporal_guard_lora.py',
               ROOT / 'projects/01-safety-constrained-coc/experiments/vlm_guard_learning/train_qwen_guard_lora.py']
    for family in ('temporal', 'static', 'maneuver'):
        for split in (('train', 'test') if family == 'temporal' else ('test',)):
            sources.extend(common.package(family) / f'{split}_{arm}.jsonl' for arm in ('p0', 'p2'))
            sources.append(common.package(family) / (f'{split}_paired.jsonl' if family == 'temporal' else 'test_contracts.jsonl'))
    sources.extend(hold_training.RUN / f'{split}.jsonl' for split in ('train', 'test'))
    sources.extend(Path(m.__file__) for m in common.worlds())
    run.mkdir(parents=True)
    write_json(run / 'protocol.json', protocol)
    for name, rows in data.items():
        (run / f'{name}.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
    write_json(run / 'RUN_MANIFEST.json', dict(project_id='guardsynth-coc', task_id=protocol['task_id'],
        run_id=run.name, status='PREPARED', created_at=datetime.now(timezone.utc).isoformat(),
        inputs=[str(p.relative_to(ROOT)) for p in sources],
        input_hashes={str(p.relative_to(ROOT)): digest(p) for p in sources},
        frozen_hashes={p.name: digest(p) for p in run.iterdir() if p.is_file()},
        model_paths={k: str(v) for k, v in MODELS.items()},
        audits={name: {mode: input_audit(rows, mode) for mode in ('rule', 'no_rule')}
                for name, rows in data.items()},
        scope=protocol['interpretation']))
    write_json(run / 'RESULT.json', dict(project_id='guardsynth-coc', task_id=protocol['task_id'],
        status='PREPARED', completed_fits=0, planned_fits=24, completed_pretrained_models=0))
    print('Frozen 736 E1 rows; 960 training rows per E2 task; 24 planned fits', flush=True)


def verify(run):
    manifest = json.loads((run / 'RUN_MANIFEST.json').read_text())
    for name, expected in manifest['input_hashes'].items():
        assert digest(ROOT / name) == expected, name
    for name, expected in manifest['frozen_hashes'].items():
        assert digest(run / name) == expected, name
    return json.loads((run / 'protocol.json').read_text())


def load_rows(run, name):
    rows = common.read_rows(run / f'{name}.jsonl')
    for row in rows:
        row['image'] = load_image(row)
        assert row['allowed_labels'] == [x for x in row['labels'] if rules(row)[x][0]]
    return rows


def semantic_loss(label_logits, allowed):
    """Categorical -log probability of the admissible set, in FP32."""
    import torch
    if label_logits.shape != allowed.shape or not allowed.any(dim=-1).all():
        raise ValueError('One or more admissible labels required per row')
    logits = label_logits.float()
    return (torch.logsumexp(logits, dim=-1)
            - torch.logsumexp(logits.masked_fill(~allowed.bool(), -torch.inf), dim=-1)).mean()


def response_label_logits(logits, labels, token_ids):
    """Autoregressive logits predicting the first supervised answer token."""
    import torch
    supervised = labels != -100
    if not supervised.any(dim=1).all():
        raise ValueError('Missing assistant label')
    first = supervised.int().argmax(dim=1)
    if (first <= 0).any():
        raise ValueError('Answer has no preceding prompt token')
    return logits[torch.arange(logits.shape[0], device=logits.device), first - 1][:, token_ids]


def encode_rows(processor, rows, mode):
    from types import SimpleNamespace
    from vlm_guard_learning.train_qwen_temporal_guard_lora import TemporalCollator
    class Collator(TemporalCollator):
        @staticmethod
        def user_message(example, mode):
            return dict(role='user', content=[dict(type='image', image=example.image),
                                              dict(type='text', text=example.text)])
    collator = Collator(processor, mode)
    encoded = []
    for row in rows:
        item = collator._encode(SimpleNamespace(image=row['image'], text=row['prompts'][mode], target=row['target']))
        target = item['labels'][item['labels'] != -100]
        assert processor.tokenizer.decode(target, skip_special_tokens=True).strip() == row['target']
        assert target[0].item() == processor.tokenizer.encode(row['target'], add_special_tokens=False)[0]
        item['allowed'] = [x in row['allowed_labels'] for x in LABELS]
        encoded.append(item)
    return encoded


def predict(model, processor, rows, mode, path):
    model.eval()
    processor.tokenizer.padding_side = 'left'
    completed = common.read_rows(path) if path.exists() else []
    assert [x['id'] for x in completed] == [x['id'] for x in rows[:len(completed)]]
    with path.open('a') as stream:
        for offset in range(len(completed), len(rows), 4):
            batch = rows[offset:offset + 4]
            texts = [x['prompts'][mode] for x in batch]
            outputs = common.generate_batch(model, processor, batch, texts, 12)
            for case, output in zip(batch, outputs):
                choice = common.parse_answer(output['text'], case['labels'])
                record = {k: case[k] for k in ('id', 'family', 'task', 'encoding', 'duration_ms', 'pair_id', 'target')}
                record.update(prediction=choice, response=output, input_mode=mode,
                    input_sha256=hashlib.sha256((case['image_sha256'] + '\n' + case['prompts'][mode]).encode()).hexdigest(),
                    **score(case, choice))
                stream.write(json.dumps(record) + '\n')
            stream.flush()
            if offset % 64 == 0 or offset + 4 >= len(rows):
                print(f'{path.parent.name}/{path.name}: {min(offset+4,len(rows))}/{len(rows)}', flush=True)


def model_record(path):
    index = path / 'model.safetensors.index.json'
    shard_names = (sorted(set(json.loads(index.read_text())['weight_map'].values()))
                   if index.exists() else ['model.safetensors'])
    if not all((path / name).is_file() for name in shard_names):
        raise FileNotFoundError(f'Missing model weight shards: {path}')
    return dict(path=str(path), revision=path.name,
                config_sha256=digest(path / 'config.json'), index_sha256=digest(index) if index.exists() else None,
                shards={name: (path/name).stat().st_size for name in shard_names})


def pretrained(run, size):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    verify(run)
    folder = run / f'pretrained_{size}'
    folder.mkdir(exist_ok=True)
    if (folder / 'COMPLETE.json').exists():
        raise FileExistsError('Pretrained evaluation already complete')
    record = model_record(MODELS[size])
    write_json(folder / 'model.json', record)
    processor = AutoProcessor.from_pretrained(MODELS[size], local_files_only=True)
    torch.manual_seed(0)
    model = Qwen3VLForConditionalGeneration.from_pretrained(MODELS[size], local_files_only=True,
        dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
    started = time.monotonic()
    rows = load_rows(run, 'pretrained_test')
    predict(model, processor, rows, 'rule', folder / 'predictions.jsonl')
    write_json(folder / 'COMPLETE.json', dict(rows=len(rows), training=False,
        elapsed_seconds=time.monotonic()-started, gpu=torch.cuda.get_device_name(0),
        cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'), torch=torch.__version__,
        transformers=__import__('transformers').__version__, model=record))


def fit(run, task, arm, seed):
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from torch.nn.utils.rnn import pad_sequence
    from torch.utils.data import DataLoader
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    sys.path.insert(0, str(ROOT / 'projects/01-safety-constrained-coc/experiments'))
    from vlm_guard_learning.train_qwen_guard_lora import language_attention_targets, seed_all
    protocol = verify(run)
    cfg = protocol['e2']
    arm_cfg = cfg['arms'][arm]
    mode = 'rule' if arm_cfg['rule_input'] else 'no_rule'
    folder = run / f'{task}_{arm}_seed{seed}'
    folder.mkdir(exist_ok=True)
    if (folder / 'COMPLETE.json').exists():
        raise FileExistsError('Fit already complete')
    seed_all(seed)
    processor = AutoProcessor.from_pretrained(common.MODEL, local_files_only=True)
    processor.tokenizer.padding_side = 'right'
    token_ids = [processor.tokenizer.encode(x, add_special_tokens=False) for x in LABELS]
    assert all(len(x) == 1 for x in token_ids)
    token_ids = [x[0] for x in token_ids]
    rows = load_rows(run, task + '_train')
    encoded = encode_rows(processor, rows, mode)
    del rows
    seed_all(seed)
    base = Qwen3VLForConditionalGeneration.from_pretrained(common.MODEL, local_files_only=True,
        dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
    model = get_peft_model(base, LoraConfig(r=cfg['lora_rank'], lora_alpha=cfg['lora_alpha'],
        lora_dropout=cfg['lora_dropout'], bias='none', task_type=TaskType.CAUSAL_LM,
        target_modules=language_attention_targets(base)))
    model.enable_input_require_grads()
    model.config.use_cache = False
    parameters = [p for p in model.parameters() if p.requires_grad]
    assert parameters and all('lora_' in name for name,p in model.named_parameters() if p.requires_grad)
    initial = hashlib.sha256(b''.join(p.detach().float().cpu().numpy().tobytes() for p in parameters)).hexdigest()
    write_json(folder / 'initialization.json', dict(seed=seed, lora_sha256=initial,
        model=model_record(common.MODEL), cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES')))
    def collate(items):
        batch = {}
        for key in ('input_ids','attention_mask','labels'):
            pad = {'input_ids':processor.tokenizer.pad_token_id,'attention_mask':0,'labels':-100}[key]
            batch[key] = pad_sequence([x[key] for x in items], batch_first=True, padding_value=pad)
        for key in ('pixel_values','image_grid_thw'):
            batch[key] = torch.cat([x[key] for x in items])
        batch['allowed'] = torch.tensor([x['allowed'] for x in items], dtype=torch.bool)
        return batch
    loader = DataLoader(encoded, batch_size=cfg['batch_size'], shuffle=True,
        generator=torch.Generator().manual_seed(seed+1000), collate_fn=collate, num_workers=0)
    optimizer = torch.optim.AdamW(parameters, lr=cfg['learning_rate'], weight_decay=cfg['weight_decay'])
    optimizer.zero_grad(set_to_none=True)
    started = time.monotonic()
    updates, history = 0, []
    for epoch in range(cfg['epochs']):
        model.train()
        sums = dict(ce=0., semantic=0., total=0.)
        count = 0
        for index,batch in enumerate(loader):
            batch = {k:v.to('cuda:0') for k,v in batch.items()}
            allowed = batch.pop('allowed')
            with torch.autocast('cuda', dtype=torch.bfloat16):
                output = model(**batch, use_cache=False)
                ce = output.loss
                sl = semantic_loss(response_label_logits(output.logits, batch['labels'], token_ids), allowed)
                loss = ce + arm_cfg['semantic_weight'] * sl
            if not torch.isfinite(loss):
                raise RuntimeError('Nonfinite loss')
            (loss / cfg['gradient_accumulation']).backward()
            n = batch['input_ids'].shape[0]
            for key,value in zip(('ce','semantic','total'), (ce,sl,loss)):
                sums[key] += float(value.detach()) * n
            count += n
            del output,loss,ce,sl,batch
            if (index+1) % cfg['gradient_accumulation'] == 0:
                torch.nn.utils.clip_grad_norm_(parameters, cfg['gradient_clip_norm'])
                optimizer.step(); optimizer.zero_grad(set_to_none=True)
                updates += 1
                if updates % 10 == 0:
                    record = dict(task=task, arm=arm, seed=seed, epoch=epoch+1, updates=updates,
                        elapsed_seconds=time.monotonic()-started, **{k:v/count for k,v in sums.items()})
                    write_json(folder / 'progress.json', record)
                    print(json.dumps(record), flush=True)
        history.append(dict(epoch=epoch+1, rows=count, **{k:v/count for k,v in sums.items()}))
    assert updates == cfg['optimizer_updates'] and all(x['rows']==960 for x in history)
    model.save_pretrained(folder / 'adapter')
    write_json(folder / 'training.json', dict(history=history, updates=updates,
        elapsed_seconds=time.monotonic()-started, initialization_sha256=initial,
        semantic_weight=arm_cfg['semantic_weight'], input_mode=mode,
        trainable_parameters=sum(p.numel() for p in parameters)))
    del encoded,loader,optimizer
    gc.collect(); torch.cuda.empty_cache()
    test = load_rows(run, task + '_test')
    predict(model, processor, test, mode, folder / 'predictions.jsonl')
    if mode == 'no_rule':
        predict(model, processor, test, 'rule', folder / 'common_rule_predictions.jsonl')
    write_json(folder / 'COMPLETE.json', dict(task=task, arm=arm, seed=seed,
        rows=len(test), status='COMPLETE', elapsed_seconds=time.monotonic()-started))


def metrics(rows):
    pairs = defaultdict(list)
    for row in rows:
        pairs[row['pair_id']].append(row)
    assert set(map(len,pairs.values())) == {2}
    return dict(rows=len(rows), accuracy=statistics.mean(x['correct'] for x in rows),
        violation_rate=sum(x['violation'] is True for x in rows)/len(rows),
        invalid_rate=statistics.mean(not x['valid'] for x in rows),
        rule_pair_accuracy=statistics.mean(all(x['correct'] for x in pair) for pair in pairs.values()))


def aggregate(run):
    protocol = verify(run)
    summary,completed_fits,completed_models = [],0,0
    for folder in sorted(run.iterdir()):
        if not folder.is_dir() or not (folder/'COMPLETE.json').exists():
            continue
        pretrained_run = folder.name.startswith('pretrained_')
        if pretrained_run:
            completed_models += 1
            detail = dict(experiment='E1', model=folder.name, arm='rule', seed=None)
        else:
            completed_fits += 1
            record = json.loads((folder/'COMPLETE.json').read_text())
            detail = dict(experiment='E2', model='2b', arm=record['arm'], seed=record['seed'])
        for filename in ('predictions.jsonl','common_rule_predictions.jsonl'):
            if not (folder/filename).exists():
                continue
            rows = common.read_rows(folder/filename)
            inputs = common.read_rows(run / ('pretrained_test.jsonl' if pretrained_run else record['task']+'_test.jsonl'))
            assert [x['id'] for x in rows] == [x['id'] for x in inputs]
            for case,row in zip(inputs,rows):
                assert row['prediction'] == common.parse_answer(row['response']['text'],case['labels'])
                assert all(row[k]==v for k,v in score(case,row['prediction']).items())
                identity = case['image_sha256']+'\n'+case['prompts'][row['input_mode']]
                assert row['input_sha256'] == hashlib.sha256(identity.encode()).hexdigest()
            groups = defaultdict(list)
            for row in rows:
                groups[row['task'],row['encoding']].append(row)
            for (task,encoding),group in groups.items():
                summary.append(dict(**detail, task=task, encoding=encoding,
                    evaluation='common_rule' if filename.startswith('common') else 'arm_input', **metrics(group)))
                for duration in sorted({x['duration_ms'] for x in group} - {None}):
                    subset = [x for x in group if x['duration_ms']==duration]
                    summary.append(dict(**detail, task=task,encoding=encoding,
                        evaluation='common_rule' if filename.startswith('common') else 'arm_input',
                        duration_ms=duration, rows=len(subset),
                        accuracy=statistics.mean(x['correct'] for x in subset),
                        violation_rate=sum(x['violation'] is True for x in subset)/len(subset),
                        invalid_rate=statistics.mean(not x['valid'] for x in subset)))
    # All arms must start from the same LoRA tensors within each task and seed.
    for task in protocol['e2']['tasks']:
        for seed in protocol['e2']['seeds']:
            initial = [json.loads(p.read_text())['lora_sha256'] for p in
                       run.glob(f'{task}_*_seed{seed}/initialization.json')]
            assert len(set(initial)) <= 1, (task,seed,'initialization mismatch')
    complete = completed_fits==protocol['e2']['planned_fits'] and completed_models==2
    result = dict(project_id='guardsynth-coc', task_id='vlm-constraint-baselines',
        status='COMPLETE' if complete else 'RUNNING', completed_fits=completed_fits,
        planned_fits=24, completed_pretrained_models=completed_models, per_seed_metrics=summary,
        interpretation=protocol['interpretation'])
    grouped = defaultdict(list)
    for row in summary:
        key = (row['experiment'],row['model'],row['arm'],row['task'],row['encoding'],
               row['evaluation'],row.get('duration_ms'))
        grouped[key].append(row)
    result['means'] = [dict(zip(('experiment','model','arm','task','encoding','evaluation','duration_ms'),key),
        seeds=[x['seed'] for x in rows], predictions=sum(x['rows'] for x in rows),
        **{k:statistics.mean(x[k] for x in rows) for k in ('accuracy','violation_rate','invalid_rate')},
        **({'rule_pair_accuracy':statistics.mean(x['rule_pair_accuracy'] for x in rows)}
            if 'rule_pair_accuracy' in rows[0] else {})) for key,rows in grouped.items()]
    write_json(run/'RESULT.json',result)
    lines=['# VLM 크기 및 semantic loss 비교', '',
           f"상태: {result['status']}; E1 완료 모델 {completed_models}/2; E2 완료 학습 {completed_fits}/24.", '',
           '동일 입력을 사용하는 규칙 조건끼리 손실 효과를 비교한다. 무규칙 조건의 정보 한계와 낮은 위반율에 의한 보수적 선택을 분리한다.', '',
           '| 실험 | 모델/조건 | 과제 | 표현 | 평가 입력 | 정확도 | 위반율 | 잘못된 출력 |',
           '|---|---|---|---|---|---:|---:|---:|']
    for row in result['means']:
        if row['duration_ms'] is not None:
            continue
        lines.append(f"| {row['experiment']} | {row['model']} / {row['arm']} | {row['task']} | {row['encoding']} | {row['evaluation']} | {100*row['accuracy']:.2f}% | {100*row['violation_rate']:.2f}% | {100*row['invalid_rate']:.2f}% |")
    lines += ['', '## 해석 범위', '',
        'E1은 기존 테스트 입력의 추가 학습 없는 비교다. E2는 두 과제 모두 같은 사전학습 모델에서 새 LoRA를 시작하므로, 과거 위치 유지의 temporal 어댑터 연속 학습과 초기화 이력이 다르다.', '',
        'Semantic loss는 Xu 등의 원리에 기반한 범주형 A–D 적용이며, 원 논문 실험의 재현이 아니다. 허용 레이블의 조건부 확률 합에만 적용하므로 임의 출력이나 실행 안전을 보장하지 않는다.', '',
        'https://proceedings.mlr.press/v80/xu18h.html',
        'https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct', '']
    (run/'REPORT_KO.md').write_text('\n'.join(lines))
    if complete:
        manifest=json.loads((run/'RUN_MANIFEST.json').read_text())
        manifest.update(status='COMPLETE',completed_at=datetime.now(timezone.utc).isoformat(),
            output_hashes={str(p.relative_to(run)):digest(p) for p in run.rglob('*')
                           if p.is_file() and p.name!='RUN_MANIFEST.json'})
        write_json(run/'RUN_MANIFEST.json',manifest)
    print(json.dumps({k:result[k] for k in ('status','completed_fits','completed_pretrained_models')}),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','pretrained','fit','aggregate'))
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--size',choices=('2b','8b'))
    parser.add_argument('--task',choices=('temporal','position_hold'))
    parser.add_argument('--arm',choices=('ce_no_rule','semantic_no_rule','ce_rule','semantic_rule'))
    parser.add_argument('--seed',type=int,choices=(42,17,123))
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'vlm-constraint-baselines-\d{4}-\d{2}-\d{2}-\d{3}',args.run_id):
        parser.error('Invalid run ID')
    run=BASE/args.run_id
    if args.action=='prepare': prepare(run)
    elif args.action=='pretrained':
        if not args.size: parser.error('--size required')
        pretrained(run,args.size)
    elif args.action=='fit':
        if not all((args.task,args.arm,args.seed)): parser.error('--task --arm --seed required')
        fit(run,args.task,args.arm,args.seed)
    else: aggregate(run)


if __name__=='__main__': main()
