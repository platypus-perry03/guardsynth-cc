"""Test frozen temporal Qwen adapters on synthetic position-hold candidates."""
import argparse
import csv
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import statistics

import run_reasoning_comparison as r

RUN = r.ROOT / "projects/04-guardsynth-coc/artifacts/public/paper1-position-hold-selection-001/position-hold-selection-2026-10-08-002"
ARMS = ("p0", "p1", "p2")
TIMES_MS = (0, 250, 500, 1000, 1500, 2000, 2100)
ENCODINGS = ("interval_maxima", "xy_waypoints")


def maximum_squared_mm(candidate, hold_ms):
    x0, y0 = candidate["xy_mm"][0]
    return max((x-x0)**2 + (y-y0)**2 for t, (x,y) in zip(TIMES_MS, candidate["xy_mm"]) if t <= hold_ms)


def reference(case):
    allowed = [c for c in case["candidates"] if maximum_squared_mm(c, case["hold_ms"]) <= 200**2]
    return max(allowed, key=lambda c: c["progress"])["label"]


def score(case, prediction):
    candidate = next((c for c in case["candidates"] if c["label"] == prediction), None)
    if candidate is None:
        return dict(valid=False, correct=False, violation=None, tolerance_violation=None, excess_m=None)
    squared = maximum_squared_mm(candidate, case["hold_ms"])
    return dict(valid=True, correct=prediction == reference(case), violation=squared > 200**2,
                tolerance_violation=squared > 210**2, excess_m=max(0., math.sqrt(squared)/1000 - .2))


def templates():
    for profile, (delta, peak_ms, safe_peak) in enumerate(itertools.product((1, 10, 11, 50), (250, 500), (199, 200))):
        excursion = [[0,0] for _ in TIMES_MS]
        excursion[TIMES_MS.index(peak_ms)] = [120+delta,160+delta]
        excursion[-1] = [1100,0]
        short_only = [[0,0],[50,0],[200,0],[200+delta,0],[100,0],[0,0],[1000,0]]
        safe_xy = [0,199] if safe_peak == 199 else [120,160]
        both_holds = [[0,0],[50,0],safe_xy,safe_xy,[50,0],safe_xy,[800,0]]
        stationary = [[0,0] for _ in TIMES_MS]
        # Vary progress values and ranking independently of the geometry roles.
        rankings = list(itertools.permutations((75,95,115)))
        progress = tuple(value + profile for value in rankings[profile % len(rankings)]) + (0,)
        behaviors = list(zip((excursion,short_only,both_holds,stationary),progress))
        for rotation in range(4):
            labels = "ABCD"[rotation:] + "ABCD"[:rotation]
            candidates = [dict(label=label, xy_mm=xy, progress=progress)
                          for label, (xy,progress) in zip(labels,behaviors)]
            candidates.sort(key=lambda c: c['label'])
            yield dict(profile=profile, delta_mm=delta, excursion_time_ms=peak_ms,
                       safe_peak_mm=safe_peak, rotation=rotation, candidates=candidates)


def model_prompt(case):
    hold = case["hold_ms"]/1000
    lines = ["Requirement CoC: Remain at the current position until the required hold period has ended, then proceed when permitted.",
             f"Constraint: Hold the ego vehicle's initial position for at least {hold:.1f} s. At every listed waypoint with t <= {hold:.1f} s, including the endpoint, the radial XY distance from the initial position must be at most 0.200 m. Movement after that period is permitted.",
             "All candidates start at (x,y)=(0,0) m at t=0 s. The diagram shows candidate radial distances over time. Numerical values below define the candidates."]
    for candidate in case["candidates"]:
        if case["encoding"] == "interval_maxima":
            small = math.sqrt(maximum_squared_mm(candidate,500))/1000
            large = math.sqrt(maximum_squared_mm(candidate,2000))/1000
            description = f"maximum radial XY distance for 0 <= t <= 0.5 s: {small:.6f} m; for 0 <= t <= 2.0 s: {large:.6f} m."
        else:
            points = "; ".join(f"({t/1000:.2f}, {x/1000:.3f}, {y/1000:.3f})"
                               for t,(x,y) in zip(TIMES_MS,candidate["xy_mm"]))
            description = f"(t in s, x in m, y in m) waypoints: {points}."
        lines.append(f"Candidate {candidate['label']}: {description} Progress score: {candidate['progress']}.")
    lines.append("Select the candidate that satisfies the constraint and has the greatest progress score among permitted candidates. Progress is a supplied synthetic utility. Answer exactly A, B, C, or D.")
    return "\n".join(lines)


def prepare():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    RUN.mkdir(parents=True,exist_ok=False)
    (RUN/"images").mkdir()
    rows=[]
    for template in templates():
        image=f"images/profile_{template['profile']:02d}_rotation_{template['rotation']}.png"
        fig, ax=plt.subplots(figsize=(5,3),constrained_layout=True)
        for c in template['candidates']:
            ax.plot([t/1000 for t in TIMES_MS],[math.hypot(x,y)/1000 for x,y in c['xy_mm']],
                    marker='o',markersize=3,label=c['label'])
        ax.set(xlabel='Prediction time (s)',ylabel='Radial XY distance (m)',xlim=(0,2.1),ylim=(0,1.15))
        ax.legend(title='Candidate',fontsize=8); ax.grid(alpha=.2)
        fig.savefig(RUN/image,dpi=100); plt.close(fig)
        for hold_ms,encoding in itertools.product((500,2000),ENCODINGS):
            row=dict(id=f"profile-{template['profile']:02d}-rotation-{template['rotation']}-{hold_ms}-{encoding}",
                     **template,hold_ms=hold_ms,encoding=encoding,image=image)
            row['target']=reference(row)
            row['prompt']=model_prompt(row)
            assert score(row,row['target'])['correct'] and not score(row,row['target'])['violation']
            rows.append(row)
    assert len(rows)==256
    (RUN/'evaluation_inputs.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
    files=[Path(__file__),Path(r.__file__)]
    for arm,seed in itertools.product(ARMS,r.SEEDS):
        adapter=r.learning('temporal')/f'{arm}-seed{seed}/adapter'
        assert (adapter/'adapter_model.safetensors').exists()
        files.extend(adapter.glob('*'))
    r.write_json(RUN/'RUN_MANIFEST.json',dict(project_id='guardsynth-coc',run_id=RUN.name,
        frozen_at=datetime.now(timezone.utc).isoformat(),model_path=str(r.MODEL),arms=ARMS,seeds=r.SEEDS,
        cases=256,geometric_profiles=16,label_rotations=4,distinct_candidate_diagrams=64,
        planned_predictions=2304,sources={str(p):r.digest(p) for p in files},
        input_hashes={str(p.relative_to(RUN)):r.digest(p) for p in [RUN/'evaluation_inputs.jsonl',*(RUN/'images').glob('*.png')]},
        inference=dict(greedy=True,batch_size=8,max_new_tokens=12,dtype='bfloat16',attention='sdpa'),
        protocol=dict(hold_ms=[500,2000],radius_mm=200,primary_tolerance_mm=0,
            secondary_measurement_tolerance_mm=10,waypoint_times_ms=TIMES_MS,
            primary_oracle='Integer squared XY distance <= 200^2 at every waypoint up to and including hold endpoint',
            reference='Highest-progress candidate admitted by primary oracle',
            encodings=ENCODINGS,rule='Same manually templated test rule for every checkpoint; not emitted by the EBLC renderer',
            controls='Same image, prompt, candidate order, rule and progress scores across P0/P1/P2; candidates listed alphabetically after behavior-label rotation; utility rankings and values vary',
            protocol_correction='Replaces unreported 001 pilot with fixed role order and progress ranks; correction decided before inspecting pilot verdicts',
            untrained_task='Position-hold radius with time; existing adapters trained on temporal entry conditions',
            new_training=False,new_human_labels=False,alpamayo=False,
            limits=['Synthetic candidate selection, not model-generated or physically executed trajectories',
                    'Checks listed waypoints; no continuous-time or dynamic-feasibility claim',
                    'Input maxima provide the geometry calculation in the summary encoding',
                    'Profiles, rotations, durations and encodings are correlated variants; not independent road scenes',
                    'No supported EBLC profile is extended and no verification-effect causal claim is made'])))
    print('Frozen 256 cases, 16 geometric profiles, 64 diagrams; 2304 planned predictions',flush=True)


def load_cases():
    from PIL import Image
    manifest=json.loads((RUN/'RUN_MANIFEST.json').read_text())
    for file,digest in manifest['sources'].items():
        assert r.digest(Path(file))==digest,file
    for file,digest in manifest['input_hashes'].items():
        assert r.digest(RUN/file)==digest,file
    rows=r.read_rows(RUN/'evaluation_inputs.jsonl')
    for row in rows:
        assert row['prompt']==model_prompt(row) and row['target']==reference(row)
        row['image']=Image.open(RUN/row['image']).convert('RGB')
    return rows


def evaluate():
    import torch
    from transformers import AutoProcessor,Qwen3VLForConditionalGeneration
    from peft import PeftModel
    assert not (RUN/'inference_result.json').exists()
    rows=load_cases()
    processor=AutoProcessor.from_pretrained(r.MODEL,local_files_only=True)
    processor.tokenizer.padding_side='left'
    torch.manual_seed(0)
    base=Qwen3VLForConditionalGeneration.from_pretrained(r.MODEL,local_files_only=True,
            dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0')
    model=None
    for arm,seed in itertools.product(ARMS,r.SEEDS):
        name=f'{arm}_seed{seed}'
        path=r.learning('temporal')/f'{arm}-seed{seed}/adapter'
        if model is None:
            model=PeftModel.from_pretrained(base,path,adapter_name=name)
        else:
            model.load_adapter(path,adapter_name=name)
        model.set_adapter(name); model.eval()
        output=RUN/f'{name}.jsonl'
        completed=r.read_rows(output) if output.exists() else []
        assert [x['id'] for x in completed]==[x['id'] for x in rows[:len(completed)]]
        with output.open('a') as stream:
            for offset in range(len(completed),len(rows),8):
                batch=rows[offset:offset+8]
                responses=r.generate_batch(model,processor,batch,[x['prompt'] for x in batch],12)
                for case,response in zip(batch,responses):
                    prediction=r.parse_answer(response['text'],'ABCD')
                    row=dict(id=case['id'],arm=arm,seed=seed,hold_ms=case['hold_ms'],encoding=case['encoding'],
                             model_text=case['prompt'],response=response,prediction=prediction,target=case['target'],
                             **score(case,prediction))
                    stream.write(json.dumps(row)+'\n')
                stream.flush()
                if offset%64==0 or offset+8>=len(rows):
                    print(f'{name}: {min(offset+8,len(rows))}/{len(rows)}',flush=True)
    load_cases()
    r.write_json(RUN/'inference_result.json',dict(status='COMPLETE',new_predictions=2304,
        gpu=torch.cuda.get_device_name(0),cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),
        torch=torch.__version__,transformers=__import__('transformers').__version__))


def report():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows={x['id']:x for x in load_cases()}
    assert json.loads((RUN/'inference_result.json').read_text())['status']=='COMPLETE'
    predictions=[]
    for arm,seed in itertools.product(ARMS,r.SEEDS):
        current=r.read_rows(RUN/f'{arm}_seed{seed}.jsonl')
        assert [x['id'] for x in current]==list(rows)
        for row in current:
            case=rows[row['id']]
            assert row['model_text']==case['prompt']
            assert row['prediction']==r.parse_answer(row['response']['text'],'ABCD')
            for key,value in score(case,row['prediction']).items():
                assert row[key]==value
        predictions.extend(current)
    assert len(predictions)==2304
    summaries=[]
    for encoding,arm,hold in itertools.product(ENCODINGS,ARMS,(500,2000)):
        group=[x for x in predictions if x['encoding']==encoding and x['arm']==arm and x['hold_ms']==hold]
        summaries.append(dict(encoding=encoding,arm=arm,hold_ms=hold,predictions=len(group),
            correct=sum(x['correct'] for x in group),violations=sum(x['violation'] is True for x in group),
            tolerance_violations=sum(x['tolerance_violation'] is True for x in group),
            invalid=sum(not x['valid'] for x in group),accuracy=statistics.mean(x['correct'] for x in group),
            violation_rate=sum(x['violation'] is True for x in group)/len(group),
            max_excess_m=max(x['excess_m'] or 0 for x in group)))
    with (RUN/'comparison_metrics.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(summaries[0]));writer.writeheader();writer.writerows(summaries)
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for ax,encoding in zip(axes,ENCODINGS):
        for i,arm in enumerate(ARMS):
            values=[next(x['violation_rate']*100 for x in summaries if x['encoding']==encoding and x['arm']==arm and x['hold_ms']==hold) for hold in (500,2000)]
            ax.bar([j+(i-1)*.23 for j in range(2)],values,width=.22,label=arm.upper())
        ax.set_xticks([0,1],['0.5 s hold','2.0 s hold'])
        ax.set(title='Provided maxima' if encoding=='interval_maxima' else 'XY waypoint lists',ylabel='Selected-candidate violations (%)',ylim=(0,105))
        ax.grid(axis='y',alpha=.2);ax.legend()
    fig.suptitle('Position-hold candidate selection: 0.200 m radius\nExisting temporal adapters; synthetic task transfer; three training seeds',fontsize=11)
    fig.savefig(RUN/'position_hold_selection.pdf');fig.savefig(RUN/'position_hold_selection.png',dpi=170);plt.close(fig)
    lines=['# 0.2m 위치 유지 후보 선택 검사','',
        '추가 학습 없이 기존 temporal P0·P1·P2 어댑터를 사용했다. 알파마요는 실행하거나 비교하지 않았다. '
        '모든 모델이 같은 그림·CoC·규칙·후보 입력을 받는다. 이 신규 거리·시간 과제는 학습 범위 밖 일반화 검사다.','',
        '0.5초 또는 2초 끝점을 포함한 모든 제시 표본에서 초기 위치와의 XY 거리가 0.200m 이하인지 검사한다. '
        '주 평가에서는 수치가 정확히 주어졌으므로 측정 허용 오차를 적용하지 않는다. 0.01m 허용 오차를 적용한 '
        '보조 위반 수도 이전 위치 유지 실험과 판정 기준을 구분하기 위해 함께 제공한다.','',
        '16개 수치 궤적 구성 × 라벨 회전 4개 × 대기 시간 2개 × 입력 표현 2개 = 256문항이다. '
        '세 모델과 학습 seed 3개에서 2,304개 응답을 생성했다. 사람이 새로 레이블링하지 않고 정수 좌표로 정답을 계산했다. '
        '64개 도식은 같은 구성의 라벨 변형이며 독립 도로 장면이 아니다.','',
        '입력 표현은 (1) 대기 구간별 최대 거리를 제공하거나 (2) (시간,x,y) 표본 좌표를 제공하는 방식이다. '
        '첫 방식은 최대 거리 계산을 이미 제공하고, 두 번째는 좌표와 시간 범위를 해석해야 한다. '
        '규칙 문장은 이번 검사를 위한 고정 템플릿이며 기존 EBLC 렌더러에서 생성한 문장이 아니다.','',
        '| 입력 | 모델 | 대기 | 정답률 | 0.200m 위반 | 0.210m 초과(보조) | 무효 | 최대 명목 한도 초과량 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        lines.append(f"| {'최대 거리 제공' if s['encoding']=='interval_maxima' else 'XY 표본 좌표'} | {s['arm'].upper()} | {s['hold_ms']/1000:.1f}초 | "
            f"{s['accuracy']*100:.2f}% | {s['violations']}/{s['predictions']} | {s['tolerance_violations']}/{s['predictions']} | {s['invalid']} | {s['max_excess_m']:.6f}m |")
    lines+=['','A–D 라벨은 회전하고 후보는 알파벳 순으로 나열한다. 합성 진행 점수의 값과 순위도 구성별로 바꾸어 고정 후보 위치와 고정 점수에 답이 연결되지 않도록 했다. 정답은 허용 후보 중 점수가 가장 큰 후보다. '
        '0.2m 경계, 구간 중간 이탈 후 복귀, 끝점 이탈, 0.5초 후·2초 전 이탈, 2초 후 이동을 포함했다.','',
        '표본별 후보 준수를 확인하는 검사이며, 모델이 새 궤적을 생성하지는 않는다. 연속 시간 궤적 준수와 차량 동역학도 입증하지 않는다. '
        '이 결과만으로 실제 0.2m 정지 유지 생성 문제가 해결되었다고 주장할 수 없다.','',
        '[비교 그래프](position_hold_selection.pdf) · [실제 입력과 좌표](evaluation_inputs.jsonl) · [CSV](comparison_metrics.csv)','']
    (RUN/'REPORT_KO.md').write_text('\n'.join(lines))
    r.write_json(RUN/'validation.json',dict(status='PASS',rescored_predictions=2304,
        source_and_input_hashes_verified=True,identical_prompts_across_checkpoints=True))
    r.write_json(RUN/'RESULT.json',dict(project_id='guardsynth-coc',status='PENDING_VISUAL_REVIEW',
        new_predictions=2304,summaries=summaries))
    print(json.dumps(summaries),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','evaluate','report'])
    args=parser.parse_args()
    {'prepare':prepare,'evaluate':evaluate,'report':report}[args.action]()
