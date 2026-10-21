"""Compare existing P0/P1/P2 adapters with identical frozen P2 rule inputs."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics

import run_reasoning_comparison as r

RUN = r.OUTPUT / "matched-temporal-rules-2026-10-08-001"
PROTOCOL = r.learning("temporal").parent / "temporal-expansion-protocol-2026-09-29-001"
ARMS = ("p0", "p1", "p2")
SPLITS = ("test", "unseen_duration")


def cases():
    from PIL import Image
    originals = {(c["scene_id"], c["contract_level"]): c for c in r.load_cases("temporal", arm="p2")}
    result = []
    for row in r.read_rows(PROTOCOL / "evaluation_p2.jsonl"):
        if row["split"] not in SPLITS:
            continue
        example = row["example"]
        scene = example["scene"]
        prior = originals[scene["scene_id"], example["contract_level"]]
        case = dict(split=row["split"], id=f"{row['split']}-{scene['scene_id']}-{example['contract_level']}",
                    scene_id=scene["scene_id"], contract_level=example["contract_level"],
                    clear_ms=round(scene["clear_time"] * 1000),
                    wait_ms=round(example["required_clear_duration"] * 1000),
                    candidates=scene["candidates"], target=example["target"],
                    image=prior["image"], image_sha256=prior["image_sha256"], prompt=row["prompt"])
        if case["split"] == "test":
            assert case["prompt"] == prior["prompt"]
        assert score(case, case["target"])["correct"]
        result.append(case)
    assert len(result) == 480
    return result


def score(case, prediction):
    release = case["clear_ms"] + case["wait_ms"]
    allowed = {c["label"]: c for c in case["candidates"] if c["entry_time"] is None
               or round(c["entry_time"] * 1000) >= release}
    reference = max(allowed, key=lambda label: allowed[label]["progress"])
    assert reference == case["target"]
    candidate = next((c for c in case["candidates"] if c["label"] == prediction), None)
    valid = candidate is not None
    deficit = 0 if not valid or candidate["entry_time"] is None else max(
        0, release - round(candidate["entry_time"] * 1000))
    return dict(correct=prediction == reference, valid=valid,
                violation=bool(deficit) if valid else None,
                waiting_shortfall_ms=deficit if valid else None,
                deferral=bool(valid and candidate["entry_time"] is None))


def freeze():
    rows = cases()
    files = [Path(__file__), Path(r.__file__), PROTOCOL / "evaluation_p2.jsonl",
             PROTOCOL / "RUN_MANIFEST.json", r.package("temporal") / "test_p2.jsonl",
             r.package("temporal") / "test_paired.jsonl"]
    files += list((r.package("temporal") / "images").glob("clear_11*.png"))
    for arm in ARMS:
        for seed in r.SEEDS:
            files += list((r.learning("temporal") / f"{arm}-seed{seed}/adapter").glob("*"))
            assert (r.learning("temporal") / f"{arm}-seed{seed}/adapter/adapter_model.safetensors").is_file()
    RUN.mkdir(exist_ok=False)
    r.write_json(RUN / "RUN_MANIFEST.json", dict(project_id="guardsynth-coc", run_id=RUN.name,
        frozen_at=datetime.now(timezone.utc).isoformat(), checkpoint_arms=ARMS, seeds=r.SEEDS,
        splits=SPLITS, examples_per_split=240, image_count=len({c['image_sha256'] for c in rows}),
        planned_predictions=len(rows) * len(ARMS) * len(r.SEEDS),
        model_path=str(r.MODEL), sources={str(p): r.digest(p) for p in files},
        inference=dict(greedy=True, batch_size=8, max_new_tokens=12, dtype="bfloat16", attention="sdpa"),
        protocol=dict(input="Exact frozen P2 image, rule, CoC and candidate prompt for every checkpoint",
                      known_waits_ms=[500, 1500], unseen_waits_ms=[800, 1800],
                      scoring="Independent integer clearance + wait gate; highest-progress allowed candidate",
                      invalid="Error with unknown admissibility; never counted as compliant",
                      training=False, new_human_labels=False, alpamayo_comparison=False,
                      limits=["Action-label selection, not trajectory generation or 0.2m position-hold compliance",
                              "Shared synthetic test images; two suites are correlated",
                              "Training exposure and checkpoint differ; verification causal benefit not isolated",
                              "P0 had rule-omitted paired training; supplied-input P0 is a specific diagnostic control"])))
    (RUN / "evaluation_inputs.jsonl").write_text("".join(json.dumps({k:v for k,v in c.items() if k != 'image'}) + '\n' for c in rows))
    print(f"Frozen {len(rows)} cases; planned {len(rows)*9} predictions", flush=True)


def verify():
    manifest = json.loads((RUN / "RUN_MANIFEST.json").read_text())
    for name, expected in manifest["sources"].items():
        assert r.digest(Path(name)) == expected, name
    rows = cases()
    stored = r.read_rows(RUN / "evaluation_inputs.jsonl")
    assert stored == [{k:v for k,v in c.items() if k != 'image'} for c in rows]
    return manifest, rows


def evaluate():
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    from peft import PeftModel
    manifest, rows = verify()
    assert not (RUN / "inference_result.json").exists()
    processor = AutoProcessor.from_pretrained(r.MODEL, local_files_only=True)
    processor.tokenizer.padding_side = "left"
    torch.manual_seed(0)
    base = Qwen3VLForConditionalGeneration.from_pretrained(r.MODEL, local_files_only=True,
                dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda:0")
    model = None
    for arm in ARMS:
        for seed in r.SEEDS:
            name = f"{arm}_seed{seed}"
            adapter = r.learning("temporal") / f"{arm}-seed{seed}/adapter"
            if model is None:
                model = PeftModel.from_pretrained(base, adapter, adapter_name=name)
            else:
                model.load_adapter(adapter, adapter_name=name)
            model.set_adapter(name)
            model.eval()
            path = RUN / f"{arm}_seed{seed}.jsonl"
            completed = r.read_rows(path) if path.exists() else []
            assert [x['id'] for x in completed] == [c['id'] for c in rows[:len(completed)]]
            with path.open("a") as stream:
                for offset in range(len(completed), len(rows), 8):
                    batch = rows[offset:offset+8]
                    outputs = r.generate_batch(model, processor, batch, [c['prompt'] for c in batch], 12)
                    for case, output in zip(batch, outputs):
                        prediction = r.parse_answer(output['text'], 'ABCD')
                        record = dict(id=case['id'], split=case['split'], scene_id=case['scene_id'],
                            contract_level=case['contract_level'], arm=arm, seed=seed,
                            image_sha256=case['image_sha256'], model_text=case['prompt'], response=output,
                            prediction=prediction, target=case['target'], wait_ms=case['wait_ms'],
                            **score(case, prediction))
                        stream.write(json.dumps(record) + '\n')
                    stream.flush()
                    if offset % 80 == 0 or offset + 8 >= len(rows):
                        print(f"{name}: {min(offset+8,len(rows))}/{len(rows)}", flush=True)
    verify()
    r.write_json(RUN / "inference_result.json", dict(status="COMPLETE", predictions=manifest['planned_predictions'],
        gpu=torch.cuda.get_device_name(0), cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),
        torch=torch.__version__, transformers=__import__('transformers').__version__))


def report():
    import csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    manifest, cases_ = verify()
    assert json.loads((RUN / "inference_result.json").read_text())["status"] == "COMPLETE"
    by_id = {c['id']:c for c in cases_}
    metrics = []
    total = 0
    for arm in ARMS:
        for seed in r.SEEDS:
            records = r.read_rows(RUN / f"{arm}_seed{seed}.jsonl")
            assert len(records) == len(cases_)
            assert [x['id'] for x in records] == list(by_id)
            for row in records:
                case = by_id[row['id']]
                assert row['model_text'] == case['prompt'] and row['image_sha256'] == case['image_sha256']
                assert row['prediction'] == r.parse_answer(row['response']['text'], 'ABCD')
                for field, value in score(case, row['prediction']).items():
                    assert row[field] == value
            total += len(records)
            for split in SPLITS:
                group = [x for x in records if x['split'] == split]
                pairs = defaultdict(list)
                for x in group:
                    pairs[x['scene_id']].append(x)
                assert all(len(pair)==2 for pair in pairs.values())
                metrics.append(dict(arm=arm, seed=seed, split=split, rows=len(group),
                    accuracy=statistics.mean(x['correct'] for x in group),
                    violation_rate=sum(x['violation'] is True for x in group)/len(group),
                    invalid_rate=statistics.mean(not x['valid'] for x in group),
                    pair_accuracy=statistics.mean(all(x['correct'] for x in pair) for pair in pairs.values()),
                    max_waiting_shortfall_ms=max(x['waiting_shortfall_ms'] or 0 for x in group),
                    violating_predictions=sum(x['violation'] is True for x in group)))
    assert total == manifest['planned_predictions']
    with (RUN / "comparison_metrics.csv").open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(metrics[0])); writer.writeheader(); writer.writerows(metrics)
    summaries=[]
    for split in SPLITS:
        for arm in ARMS:
            group=[m for m in metrics if m['split']==split and m['arm']==arm]
            summaries.append(dict(arm=arm, split=split, predictions=sum(m['rows'] for m in group),
                **{field:statistics.mean(m[field] for m in group) for field in ['accuracy','violation_rate','invalid_rate','pair_accuracy']},
                violation_count=sum(m['violating_predictions'] for m in group),
                max_waiting_shortfall_ms=max(m['max_waiting_shortfall_ms'] for m in group)))
    fig, axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    colors=['#777777','#c38b30','#276fbf']
    for ax, field, title in zip(axes,['accuracy','violation_rate'],['Reference accuracy (%)','Early-entry violations (%)']):
        for i, arm in enumerate(ARMS):
            xs=[j+(i-1)*.23 for j in range(2)]
            values=[next(s[field]*100 for s in summaries if s['arm']==arm and s['split']==split) for split in SPLITS]
            ax.bar(xs,values,width=.22,label=arm.upper()+' + same CNL',color=colors[i])
            for x,split in zip(xs,SPLITS):
                points=[m[field]*100 for m in metrics if m['arm']==arm and m['split']==split]
                ax.scatter([x-.035,x,x+.035],points,color='black',s=15,zorder=3)
        ax.set_xticks([0,1],['Known: 0.5 / 1.5 s','Unseen: 0.8 / 1.8 s'])
        ax.set_title(title); ax.set_ylim(0,105); ax.grid(axis='y',alpha=.2)
    axes[0].legend(fontsize=8,loc='lower left')
    fig.suptitle('Identical rule-bearing inputs; existing Qwen3-VL LoRA checkpoints\nBars: three-seed means; dots: individual seeds',fontsize=11)
    fig.savefig(RUN/'matched_temporal_comparison.pdf'); fig.savefig(RUN/'matched_temporal_comparison.png',dpi=170)
    plt.close(fig)
    lines=['# 동일 제약 입력에서 P0·P1·P2 비교','',
        '알파마요는 비교에서 제외했다. 기존 Qwen3-VL-2B-Instruct LoRA 체크포인트 9개를 사용하고 새 학습은 하지 않았다. '
        '세 조건 모두 정확히 같은 P2 이미지·CoC·CNL·행동 후보 문장을 입력받는다. 답은 A–D 후보 라벨이다.','',
        'P0는 CoC만으로 학습한 모델에 평가 때 CNL을 제공한 조건이다. P1은 자연어 제약을 포함해 학습한 모델, '
        'P2는 EBLC 유래 CNL을 포함해 학습한 모델이다. 이번에는 입력 표현을 모두 같은 CNL로 통일했다.','',
        '기존 동결 평가셋의 test 240행과 unseen_duration 240행을 사용했다. 세 학습 seed(42,17,123)에서 총 4,320개 응답을 새로 생성했다. '
        '두 평가 묶음은 동일한 10개 합성 이미지를 공유한다. 미학습 대기 시간 묶음은 후보 진입 시각도 0.3초 이동한 기존 평가 변형이다.','',
        '| 평가 대기 시간 | 모델(모두 같은 CNL 제공) | 정답률 | 조기 진입 위반율 | 위반 수 | 계약 쌍 정답률 | 무효 응답률 | 최대 대기 부족량 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        lines.append(f"| {'0.5 / 1.5초' if s['split']=='test' else '0.8 / 1.8초'} | {s['arm'].upper()} | "
                     f"{s['accuracy']*100:.2f}% | {s['violation_rate']*100:.2f}% | {s['violation_count']}/{s['predictions']} | "
                     f"{s['pair_accuracy']*100:.2f}% | {s['invalid_rate']*100:.2f}% | {s['max_waiting_shortfall_ms']/1000:.3f}초 |")
    lines+=['','정답은 허용 후보 중 진행 점수가 가장 큰 후보이다. 진입 시각이 구역 해제 시각 + 요구 대기 시간보다 빠르면 위반이다. '
        '최대 대기 부족량은 그 차이의 최댓값이다. 무효 응답은 정답 오류이며 준수 여부 미확인으로 따로 집계한다.','',
        '이 결과는 제약을 읽고 행동 후보를 고르는 문제에 대한 검사다. 0.2m 위치 유지나 2초 정지 궤적 생성의 해결을 입증하지 않는다. '
        'P0는 규칙이 빠진 쌍별 입력으로 학습했으며 세 모델은 학습 정보와 체크포인트가 다르므로 검증 자체의 인과적 효과를 분리한 실험도 아니다.','',
        '[비교 그래프](matched_temporal_comparison.pdf) · [seed별 CSV](comparison_metrics.csv) · [실제 입력](evaluation_inputs.jsonl)','']
    (RUN/'REPORT_KO.md').write_text('\n'.join(lines))
    r.write_json(RUN/'validation.json',dict(status='PASS',rescored_predictions=total,
        exact_prompt_and_image_agreement=True,all_frozen_hashes_verified=True))
    r.write_json(RUN/'RESULT.json',dict(project_id='guardsynth-coc',status='PENDING_VISUAL_REVIEW',
        new_predictions=total,summaries=summaries,metrics=metrics))
    print(json.dumps(summaries),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['freeze','evaluate','report'])
    args=parser.parse_args()
    {'freeze':freeze,'evaluate':evaluate,'report':report}[args.action]()
