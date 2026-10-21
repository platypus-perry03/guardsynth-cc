"""Matched position-hold continuation training and frozen synthetic evaluation."""
import argparse
import csv
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time

import run_reasoning_comparison as common
import run_position_hold_selection as diagnostic
import position_hold_training_profile as profile

RUN = common.ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-position-hold-training-001/position-hold-training-2026-10-08-001'
ARMS = ('p0', 'p1', 'p2')
SPLITS = {'train': 120, 'validation': 16, 'test': 32}
COC = 'Remain at the current position until the required hold period has ended, then proceed when permitted.'
BUDGET = dict(epochs=3, batch_size=2, accumulation=8, learning_rate=0.0002,
              weight_decay=0.01, lora_rank=8, lora_alpha=16, lora_dropout=0.05,
              training_rows=960, optimizer_updates=180, checkpoint='fixed final epoch')


def natural_rule(hold_ms):
    return (f'For the first {hold_ms / 1000:.1f} seconds, keep the vehicle within 0.200 metres '
            'of its starting point at all listed times, including the final time of this '
            'waiting period. Moving farther away is allowed only after this period ends.')


def prompt(case, arm='p2'):
    # Reuse candidate formatting, selection objective and diagram description.
    text = diagnostic.model_prompt(case)
    lines = text.splitlines()
    lines[0] = 'Requirement CoC: ' + COC
    if arm == 'p0':
        del lines[1]
    elif arm == 'p1':
        lines[1] = 'Constraint: ' + natural_rule(case['hold_ms'])
    elif arm == 'p2':
        lines[1] = 'Constraint: ' + profile.render(profile.contract(case['hold_ms']))
    else:
        raise ValueError(arm)
    return '\n'.join(lines)


def geometry_key(candidates):
    return json.dumps(sorted(c['xy_mm'] for c in candidates), separators=(',', ':'))


def generate_profiles(count, seed, forbidden):
    rng = random.Random(seed)
    result = []
    directions = ((1, 0, 1), (0, 1, 1), (3, 4, 5), (-3, 4, 5), (4, -3, 5))
    def point(radius):
        x, y, divisor = rng.choice(directions)
        return [round(x * radius / divisor), round(y * radius / divisor)]
    while len(result) < count:
        safe = [[0, 0]] + [point(rng.choice((0, 50, 100, 150, 180, 190, 199, 200))) for _ in range(5)] + [point(rng.randint(400, 1000))]
        # Exact-boundary safe points use integer Pythagorean triples.
        if rng.random() < .5:
            safe[rng.randint(1, 5)] = rng.choice(([200, 0], [120, 160], [-160, 120]))
        short = [[0, 0]] + [point(rng.randint(0, 190)) for _ in range(5)] + [point(rng.randint(400, 1000))]
        short[rng.choice((3, 4, 5))] = point(rng.randint(220, 400))
        early = [[0, 0]] + [point(rng.randint(0, 190)) for _ in range(5)] + [point(rng.randint(400, 1000))]
        early[rng.choice((1, 2))] = point(rng.randint(220, 400))
        extra = [[0, 0]] + [point(rng.randint(0, 190)) for _ in range(5)] + [point(rng.randint(400, 1000))]
        if rng.random() < .5:
            extra[rng.randint(1, 5)] = point(rng.randint(220, 400))
        utilities = rng.sample(range(20, 151), 4)
        # Keep the extra safe candidate lower ranked; half of duration pairs
        # deliberately have different targets. All utility numbers still vary.
        low, high = sorted(utilities[:2])
        safe_score, short_score = (low, high) if len(result) % 2 == 0 else (high, low)
        extra_score = min(utilities) - 1
        candidates = [dict(xy_mm=xy, progress=value) for xy, value in
                      zip((safe, short, early, extra), (safe_score, short_score, utilities[2], extra_score))]
        key = geometry_key(candidates)
        if key in forbidden:
            continue
        forbidden.add(key)
        labels = rng.sample(list('ABCD'), 4)
        for c, label in zip(candidates, labels):
            c['label'] = label
        result.append(candidates)
    return result


def diagram(candidates, path):
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (512, 288), 'white')
    draw = ImageDraw.Draw(image)
    left, top, width, height = 58, 35, 410, 200
    draw.text((90, 8), 'Candidate radial XY distance over time', fill='black')
    draw.line((left, top, left, top + height, left + width, top + height), fill='black', width=2)
    for t in (0, 500, 1000, 1500, 2000):
        x = left + width * t / 2100
        draw.text((x - 10, top + height + 5), f'{t / 1000:g}', fill='black')
    for radius in (0, .2, .5, 1):
        y = top + height * (1 - radius / 1.1)
        draw.line((left, y, left + width, y), fill='#dddddd')
        draw.text((20, y - 4), f'{radius:g}', fill='black')
    for c, color in zip(candidates, ('#0072b2', '#d55e00', '#009e73', '#cc79a7')):
        points = [(left + width * t / 2100, top + height * (1 - math.hypot(*xy) / 1100))
                  for t, xy in zip(profile.TIMES_MS, c['xy_mm'])]
        draw.line(points, fill=color, width=2)
        draw.text((385 + 22 * 'ABCD'.index(c['label']), 20), c['label'], fill=color)
    draw.text((230, 266), 'Time (s)', fill='black')
    draw.text((4, 16), 'm', fill='black')
    image.save(path)


def prepare():
    RUN.mkdir(parents=True, exist_ok=False)
    (RUN / 'images').mkdir()
    forbidden = {geometry_key(t['candidates']) for t in diagnostic.templates()}
    all_rows = {}
    for split_index, (split, count) in enumerate(SPLITS.items()):
        templates = generate_profiles(count, 2026100800 + split_index, forbidden)
        rows = []
        for i, candidates in enumerate(templates):
            for rotation in (0, 2):
                rotated = [dict(c, label='ABCD'[('ABCD'.index(c['label']) + rotation) % 4]) for c in candidates]
                rotated.sort(key=lambda c: c['label'])
                image = f'images/{split}_{i:03d}_{rotation}.png'
                diagram(rotated, RUN / image)
                for hold_ms, encoding in itertools.product((500, 2000), diagnostic.ENCODINGS):
                    row = dict(id=f'{split}-{i:03d}-{rotation}-{hold_ms}-{encoding}',
                               profile_id=f'{split}-{i:03d}', candidates=rotated,
                               hold_ms=hold_ms, encoding=encoding, image=image)
                    row['target'] = diagnostic.reference(row)
                    row['prompts'] = {arm: prompt(row, arm) for arm in ARMS}
                    row['eblc'] = profile.contract(hold_ms)
                    rows.append(row)
        (RUN / f'{split}.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        all_rows[split] = rows
    assert len(all_rows['train']) == BUDGET['training_rows']
    compiled = {hold: profile.compile_contract(profile.contract(hold)) for hold in (500, 2000)}
    checks = []
    for rows in all_rows.values():
        for row in rows:
            verdicts = {c['label']: profile.verdict(compiled[row['hold_ms']], c) for c in row['candidates']}
            expected = {c['label']: ('SAT' if diagnostic.maximum_squared_mm(c, row['hold_ms']) <= 40000 else 'UNSAT') for c in row['candidates']}
            assert verdicts == expected, row['id']
            assert verdicts[row['target']] == 'SAT'
            checks.append(dict(id=row['id'], verdicts=verdicts, reference=row['target']))
    (RUN / 'specification_checks.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in checks))
    for hold, core in compiled.items():
        common.write_json(RUN / f'core_{hold}.json', profile.lower(profile.contract(hold)))
        import z3
        solver = z3.Solver()
        solver.add(*[a.expression for a in core.assertions])
        (RUN / f'contract_{hold}.smt2').write_text(solver.to_smt2())
    files = [Path(__file__), Path(profile.__file__), Path(diagnostic.__file__), Path(common.__file__),
             common.ROOT / 'projects/04-guardsynth-coc/tests/test_position_hold_training.py',
             common.ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/core_ir.py',
             common.ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/smt_compiler.py',
             common.ROOT / 'projects/01-safety-constrained-coc/experiments/vlm_guard_learning/train_qwen_temporal_guard_lora.py',
             common.ROOT / 'projects/01-safety-constrained-coc/experiments/vlm_guard_learning/train_qwen_guard_lora.py',
             diagnostic.RUN / 'evaluation_inputs.jsonl', diagnostic.RUN / 'RUN_MANIFEST.json']
    files.extend((diagnostic.RUN / 'images').glob('*.png'))
    for arm, seed in itertools.product(ARMS, common.SEEDS):
        files.extend((common.learning('temporal') / f'{arm}-seed{seed}/adapter').glob('*'))
    common.write_json(RUN / 'RUN_MANIFEST.json', dict(
        project_id='guardsynth-coc', run_id=RUN.name, frozen_at=datetime.now(timezone.utc).isoformat(),
        model_path=str(common.MODEL), arms=ARMS, seeds=common.SEEDS, budget=BUDGET,
        sources={str(p): common.digest(p) for p in files},
        input_hashes={str(p.relative_to(RUN)): common.digest(p) for p in RUN.rglob('*') if p.is_file()},
        protocol=dict(training='Continue each corresponding temporal adapter; no new human labels',
            train_input={'p0': 'CoC only', 'p1': 'CoC + natural language supplied rule', 'p2': 'CoC + validated EBLC-derived CNL'},
            evaluation_input='Identical P2 CNL, image and candidates for all arms before and after training',
            fresh_split_profiles=SPLITS, split_rows={s: len(rows) for s, rows in all_rows.items()},
            grouping='Whole geometry profile, all label/duration/encoding variants kept in one split',
            diagnostic_regression='Previously inspected 256 cases; excluded from training and primary test',
            primary_radius_mm=200, secondary_tolerance_mm=10, hold_ms=[500, 2000],
            candidate_smt_checks=len(checks) * 4, validation='Reserved; not used to select epochs or hyperparameters',
            encodings=diagnostic.ENCODINGS, alpamayo=False,
            limits=['Synthetic A-D selection; no trajectory generation or vehicle control',
                    'Checks listed samples, not continuous time',
                    'All splits use the same generator family; no real-scene generalization claim',
                    'P0 training omits the distinguishing rule; not identical-information training',
                    'No causal separation of EBLC verification from CNL wording'])))
    common.write_json(RUN / 'RESULT.json', dict(status='PREPARED', project_id='guardsynth-coc'))
    print('Frozen 960 train / 128 reserved validation / 256 test rows; 5376 candidate SMT checks', flush=True)


def verify_frozen():
    manifest = json.loads((RUN / 'RUN_MANIFEST.json').read_text())
    for name, digest in manifest['sources'].items():
        assert common.digest(Path(name)) == digest, name
    for name, digest in manifest['input_hashes'].items():
        assert common.digest(RUN / name) == digest, name


def load_cases(split):
    from PIL import Image
    rows = common.read_rows(RUN / f'{split}.jsonl')
    for row in rows:
        assert row['target'] == diagnostic.reference(row)
        assert row['prompts'] == {arm: prompt(row, arm) for arm in ARMS}
        row['image'] = Image.open(RUN / row['image']).convert('RGB')
    return rows


def encode_training(processor, rows, arm):
    from vlm_guard_learning.train_qwen_temporal_guard_lora import TemporalCollator
    from types import SimpleNamespace
    class Collator(TemporalCollator):
        @staticmethod
        def user_message(example, mode):
            return {'role': 'user', 'content': [{'type': 'image', 'image': example.image},
                                               {'type': 'text', 'text': example.text}]}
    collator = Collator(processor, arm)
    encoded = [collator._encode(SimpleNamespace(image=row['image'], text=row['prompts'][arm], target=row['target'])) for row in rows]
    for item, row in zip(encoded, rows):
        labels = item['labels'][item['labels'] != -100]
        assert len(labels) >= 2
        assert processor.tokenizer.decode(labels, skip_special_tokens=True).strip() == row['target']
    return encoded


def train_fit(model, processor, encoded, arm, seed):
    import torch
    from torch.nn.utils.rnn import pad_sequence
    from torch.utils.data import DataLoader
    from vlm_guard_learning.train_qwen_guard_lora import seed_all
    seed_all(seed)
    processor.tokenizer.padding_side = 'right'
    pad_id = processor.tokenizer.pad_token_id
    def collate(items):
        return {key: (torch.cat([item[key] for item in items]) if key in ('pixel_values', 'image_grid_thw') else
                      pad_sequence([item[key] for item in items], batch_first=True,
                                   padding_value={'input_ids': pad_id, 'attention_mask': 0, 'labels': -100}[key]))
                for key in items[0]}
    loader = DataLoader(encoded, batch_size=BUDGET['batch_size'], shuffle=True,
                        generator=torch.Generator().manual_seed(seed + 1000), collate_fn=collate, num_workers=0)
    parameters = [p for p in model.parameters() if p.requires_grad]
    assert parameters and all('lora_' in name for name, p in model.named_parameters() if p.requires_grad)
    optimizer = torch.optim.AdamW(parameters, lr=BUDGET['learning_rate'], weight_decay=BUDGET['weight_decay'])
    optimizer.zero_grad(set_to_none=True)
    history = []
    started = time.monotonic()
    updates = 0
    model.config.use_cache = False
    for epoch in range(BUDGET['epochs']):
        model.train()
        loss_sum = 0.
        examples = 0
        for batch_index, batch in enumerate(loader):
            batch = {key: value.to('cuda:0') for key, value in batch.items()}
            with torch.autocast('cuda', dtype=torch.bfloat16):
                loss = model(**batch, use_cache=False).loss
            if not torch.isfinite(loss):
                raise RuntimeError('nonfinite training loss')
            (loss / BUDGET['accumulation']).backward()
            n = batch['input_ids'].shape[0]
            loss_sum += float(loss.detach()) * n
            examples += n
            if (batch_index + 1) % BUDGET['accumulation'] == 0:
                torch.nn.utils.clip_grad_norm_(parameters, 1.)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                updates += 1
                if updates % 10 == 0:
                    progress = dict(arm=arm, seed=seed, epoch=epoch + 1, updates=updates,
                                    mean_loss=loss_sum / examples, elapsed_seconds=time.monotonic() - started)
                    common.write_json(RUN / 'training_progress.json', progress)
                    print(json.dumps(progress), flush=True)
        history.append(dict(epoch=epoch + 1, mean_loss=loss_sum / examples, examples=examples))
    assert updates == BUDGET['optimizer_updates']
    return dict(history=history, optimizer_updates=updates, elapsed_seconds=time.monotonic() - started,
                trainable_parameters=sum(p.numel() for p in parameters), assistant_only_labels=True)


def predict(model, processor, cases, path, arm, seed, phase):
    model.eval()
    processor.tokenizer.padding_side = 'left'
    done = common.read_rows(path) if path.exists() else []
    assert [row['id'] for row in done] == [row['id'] for row in cases[:len(done)]]
    with path.open('a') as stream:
        for offset in range(len(done), len(cases), 8):
            batch = cases[offset:offset + 8]
            texts = [prompt(row, 'p2') for row in batch]
            responses = common.generate_batch(model, processor, batch, texts, 12)
            for row, text, response in zip(batch, texts, responses):
                choice = common.parse_answer(response['text'], 'ABCD')
                record = dict(id=row['id'], arm=arm, seed=seed, phase=phase, hold_ms=row['hold_ms'],
                              encoding=row['encoding'], model_text=text, target=row['target'],
                              prediction=choice, response=response, **diagnostic.score(row, choice))
                stream.write(json.dumps(record) + '\n')
            stream.flush()
    print(f'{arm} seed {seed} {phase}: {len(cases)} predictions', flush=True)


def run():
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from peft import PeftModel
    sys.path.insert(0, str(common.ROOT / 'projects/01-safety-constrained-coc/experiments'))
    verify_frozen()
    assert not (RUN / 'evaluation_complete.json').exists()
    processor = AutoProcessor.from_pretrained(common.MODEL, local_files_only=True)
    training, test = load_cases('train'), load_cases('test')
    regression = common.read_rows(diagnostic.RUN / 'evaluation_inputs.jsonl')
    from PIL import Image
    for row in regression:
        assert row['prompt'] == prompt(row, 'p2')
        row['image'] = Image.open(diagnostic.RUN / row['image']).convert('RGB')
    encoded_cache = {}
    base = Qwen3VLForConditionalGeneration.from_pretrained(common.MODEL, local_files_only=True,
        dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda:0')
    model = None
    for arm, seed in itertools.product(ARMS, common.SEEDS):
        name = f'{arm}_seed{seed}'
        folder = RUN / name
        folder.mkdir(exist_ok=True)
        completed_fit = (folder / 'training.json').exists()
        adapter = folder / 'adapter' if completed_fit else common.learning('temporal') / f'{arm}-seed{seed}/adapter'
        if model is None:
            model = PeftModel.from_pretrained(base, adapter, adapter_name=name, is_trainable=not completed_fit)
        else:
            model.load_adapter(adapter, adapter_name=name, is_trainable=not completed_fit)
        model.set_adapter(name)
        if not completed_fit:
            predict(model, processor, test, folder / 'before_test.jsonl', arm, seed, 'before_test')
            processor.tokenizer.padding_side = 'right'
            if arm not in encoded_cache:
                encoded_cache[arm] = encode_training(processor, training, arm)
                print(f'{arm}: assistant-only encoding verified for 960 training rows', flush=True)
            model.enable_input_require_grads()
            record = train_fit(model, processor, encoded_cache[arm], arm, seed)
            model.save_pretrained(folder / 'adapter', selected_adapters=[name])
            # PEFT names non-default adapters in a subdirectory.
            nested = folder / 'adapter' / name
            if nested.exists():
                for file in nested.iterdir():
                    file.rename(folder / 'adapter' / file.name)
                nested.rmdir()
            common.write_json(folder / 'training.json', record)
            print(f'{name}: saved fixed final-epoch adapter', flush=True)
        predict(model, processor, test, folder / 'after_test.jsonl', arm, seed, 'after_test')
        predict(model, processor, regression, folder / 'after_regression.jsonl', arm, seed, 'after_regression')
        # Remove the completed adapter before loading the next fit.
        model.delete_adapter(name)
        torch.cuda.empty_cache()
    verify_frozen()
    common.write_json(RUN / 'evaluation_complete.json', dict(status='COMPLETE', fits=9,
        predictions=6912, gpu=torch.cuda.get_device_name(0), cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),
        torch=torch.__version__, transformers=__import__('transformers').__version__))


def report():
    verify_frozen()
    assert json.loads((RUN / 'evaluation_complete.json').read_text())['status'] == 'COMPLETE'
    case_sets = {'before_test': common.read_rows(RUN / 'test.jsonl'), 'after_test': common.read_rows(RUN / 'test.jsonl'),
                 'after_regression': common.read_rows(diagnostic.RUN / 'evaluation_inputs.jsonl')}
    predictions = []
    for arm, seed in itertools.product(ARMS, common.SEEDS):
        folder = RUN / f'{arm}_seed{seed}'
        record = json.loads((folder / 'training.json').read_text())
        assert record['optimizer_updates'] == 180
        for phase, cases in case_sets.items():
            current = common.read_rows(folder / f'{phase}.jsonl')
            assert [row['id'] for row in current] == [row['id'] for row in cases]
            for row, case in zip(current, cases):
                assert row['model_text'] == prompt(case, 'p2')
                assert row['prediction'] == common.parse_answer(row['response']['text'], 'ABCD')
                assert all(row[key] == value for key, value in diagnostic.score(case, row['prediction']).items())
            predictions.extend(current)
    summaries = []
    for phase, encoding, arm, hold in itertools.product(case_sets, diagnostic.ENCODINGS, ARMS, (500, 2000)):
        rows = [x for x in predictions if (x['phase'], x['encoding'], x['arm'], x['hold_ms']) == (phase, encoding, arm, hold)]
        summaries.append(dict(phase=phase, encoding=encoding, arm=arm, hold_ms=hold, predictions=len(rows),
            correct=sum(x['correct'] for x in rows), violations=sum(x['violation'] is True for x in rows),
            tolerance_violations=sum(x['tolerance_violation'] is True for x in rows),
            invalid=sum(not x['valid'] for x in rows), accuracy=statistics.mean(x['correct'] for x in rows),
            violation_rate=sum(x['violation'] is True for x in rows) / len(rows),
            max_excess_m=max(x['excess_m'] or 0 for x in rows)))
    with (RUN / 'comparison_metrics.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0])); writer.writeheader(); writer.writerows(summaries)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for column, encoding in enumerate(diagnostic.ENCODINGS):
        for row, metric in enumerate(('accuracy', 'violation_rate')):
            ax = axes[row, column]
            for i, arm in enumerate(ARMS):
                values = [statistics.mean(s[metric] for s in summaries if s['phase'] == phase and s['encoding'] == encoding and s['arm'] == arm) * 100 for phase in ('before_test', 'after_test')]
                ax.bar([j + (i - 1) * .23 for j in range(2)], values, width=.22, label=arm.upper())
            ax.set_xticks((0, 1), ('Before training', 'After training'))
            ax.set(ylim=(0, 105), ylabel='Accuracy (%)' if metric == 'accuracy' else 'Constraint violations (%)',
                   title='Supplied interval maxima' if encoding == 'interval_maxima' else 'XY waypoint lists')
            ax.legend(); ax.grid(axis='y', alpha=.2)
    fig.suptitle('Position-hold candidate selection: matched rule at evaluation\nFresh held-out synthetic geometries; three seeds; 0.5 s and 2.0 s holds')
    fig.savefig(RUN / 'position_hold_training.pdf', bbox_inches='tight')
    fig.savefig(RUN / 'position_hold_training.png', dpi=170, bbox_inches='tight'); plt.close(fig)
    lines = ['# 위치 유지 과제 추가 학습 및 재평가', '',
             '기존 temporal 어댑터 9개를 각각 960개 위치 유지 사례로 3 epoch 추가 학습했다. '
             '각 fit은 180 optimizer update이며 마지막 epoch를 고정 사용했다. '
             '모델은 A–D 후보를 선택한다. XY 궤적 생성·실차 제어·알파마요 비교 실험은 아니다.', '',
             'P0 학습 입력은 원래 CoC, P1은 CoC+자연어 규칙, P2는 CoC+새 제한적 위치 유지 EBLC에서 생성한 CNL이다. '
             '평가에서는 모든 조건에 동일 P2 CNL을 제공한다. 검증 여부와 문구 효과를 독립적으로 분리한 실험은 아니다.', '',
             '학습 120 geometry profile/960행, validation 16 profile/128행, 테스트 32 profile/256행이다. '
             '같은 profile의 label rotation·duration·encoding은 같은 split에 둔다. '
             'validation은 보관만 하고 checkpoint 선택에 사용하지 않았다. '
             '추가 사람 라벨링 없이 합성 궤적·규칙으로 기준 정답을 자동 계산했다. '
             '각 profile은 두 label rotation × 두 대기 시간 × 두 표현 방식의 8개 관련 사례를 낳으므로 행은 독립 도로 장면이 아니다.', '',
             '별도 integer oracle은 모든 검사 시점의 x²+y²≤200²를 평가하며, 5376개 후보에서 SMT 판정과 일치했다. '
             '0.5/2.0초 끝점을 포함하며 중간에 밖으로 나갔다가 돌아오는 경우도 위반이다. '
             '0.01m 측정 허용오차는 보조 지표로 별도 기록한다.', '',
             '|집합|표현|조건|대기|정답/192|위반/192|0.01m 허용 후 위반|최대 초과(m)|',
             '|---|---|---|---|---:|---:|---:|---:|']
    for s in summaries:
        lines.append(f"|{s['phase']}|{s['encoding']}|{s['arm'].upper()}|{s['hold_ms']/1000:.1f}s|{s['correct']}|{s['violations']}|{s['tolerance_violations']}|{s['max_excess_m']:.6f}|")
    lines.extend(['', 'before_test/after_test는 같은 새 테스트셋·같은 입력에서 학습 전후를 비교한다. '
                  'after_regression은 이미 관찰한 이전 256개 사례의 회귀 검사이며 새로운 독립 테스트로 주장하지 않는다. '
                  '학습으로 관측 위반이 감소하더라도 모든 상황에서 준수한다는 보장은 아니다. '
                  '숫자 입력을 이용하는 합성 과제이며 실영상 일반화·연속 시간 안전성은 검사하지 않았다.', ''])
    (RUN / 'REPORT_KO.md').write_text('\n'.join(lines))
    common.write_json(RUN / 'RESULT.json', dict(status='COMPLETE', project_id='guardsynth-coc', fits=9,
        training_rows_per_fit=960, optimizer_updates_per_fit=180, predictions=len(predictions), summaries=summaries,
        validation='All predictions independently rescored; source and input hashes verified',
        output_hashes={str(p.relative_to(RUN)): common.digest(p) for p in RUN.rglob('*')
                       if p.is_file() and p.name not in ('RESULT.json', 'RUN_MANIFEST.json')}))
    print(json.dumps(summaries, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'run', 'report'))
    args = parser.parse_args()
    {'prepare': prepare, 'run': run, 'report': report}[args.command]()
