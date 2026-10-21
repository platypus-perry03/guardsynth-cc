"""Audit and plot the completed, frozen E1/E2 baseline experiment."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

import run_vlm_constraint_baselines as baseline
import run_vlm_generation_budget as generation
import run_vlm_batched_diagnostic as batched
import resume_vlm_constraint_baselines as recovery


ARMS = ('ce_no_rule', 'semantic_no_rule', 'ce_rule', 'semantic_rule')
ARM_NAMES = ('CE / no rule', 'CE + semantic / no rule', 'CE / CNL', 'CE + semantic / CNL')
GROUPS = (('temporal', 'candidate_scalars'), ('position_hold', 'interval_maxima'),
          ('position_hold', 'xy_waypoints'))
GROUP_NAMES = ('Temporal entry', 'Position hold: maxima', 'Position hold: XY')


def read(path):
    return json.loads(path.read_text())


def summarize(rows):
    return dict(rows=len(rows), correct=sum(x['correct'] for x in rows),
        violations=sum(x['violation'] is True for x in rows),
        invalid=sum(not x['valid'] for x in rows),
        accuracy=statistics.mean(x['correct'] for x in rows),
        violation_rate=sum(x['violation'] is True for x in rows)/len(rows),
        invalid_rate=statistics.mean(not x['valid'] for x in rows))


def audit(run):
    protocol = baseline.verify(run)
    assert read(run/'RESULT.json')['status'] == 'COMPLETE'
    resumed = read(run/'execution_recovery.json')
    assert resumed['return_codes'] == [0]*4
    assert resumed['source_sha256'] == baseline.digest(Path(recovery.__file__))
    diagnostic = read(run/'generation_budget_diagnostic/protocol.json')
    assert diagnostic['source'] == baseline.digest(Path(generation.__file__))
    assert diagnostic['test_sha256'] == baseline.digest(run/'pretrained_test.jsonl')
    e1, e2, inputs = [], [], []
    parameter_counts=set()
    source_rows = baseline.common.read_rows(run/'pretrained_test.jsonl')
    for size in ('2b', '8b'):
        for budget in (12, 512):
            folder = run/f'pretrained_{size}' if budget == 12 else run/'generation_budget_diagnostic'/('2b_batch8' if size=='2b' else size)
            records = baseline.common.read_rows(folder/'predictions.jsonl')
            assert len(records) == len(source_rows) == 736
            assert (folder/'COMPLETE.json').exists()
            if budget == 512:
                assert baseline.digest(folder/'predictions.jsonl') == read(folder/'COMPLETE.json')['output_sha256']
                if size=='2b':
                    amendment=read(folder/'protocol.json')
                    assert amendment['source_sha256']==baseline.digest(Path(batched.__file__))
                    assert amendment['parser_source_sha256']==baseline.digest(Path(generation.__file__))
                    assert amendment['test_sha256']==baseline.digest(run/'pretrained_test.jsonl')
                    partial=baseline.ROOT/amendment['excluded_partial']['path']
                    assert baseline.digest(partial)==amendment['excluded_partial']['sha256']
                    assert len(baseline.common.read_rows(partial))==amendment['excluded_partial']['rows']
                    inputs.append(partial)
                    inputs.append(folder/'protocol.json')
            inputs.extend((folder/'predictions.jsonl', folder/'COMPLETE.json'))
            grouped = defaultdict(list)
            for case, row in zip(source_rows, records):
                assert case['id'] == row['id']
                parser = generation.parse_final if budget == 512 else baseline.common.parse_answer
                assert parser(row['response']['text'], case['labels']) == row['prediction']
                assert all(row[k] == v for k, v in baseline.score(case, row['prediction']).items())
                if budget == 512:
                    strict = baseline.common.parse_answer(row['response']['text'], case['labels'])
                    assert strict == row['strict_prediction']
                    assert baseline.score(case, strict) == row['strict_score']
                grouped[row['task'], row['encoding']].append(row)
            for (task, encoding), rows in grouped.items():
                item = dict(model=size, max_new_tokens=budget,batch_size=(4 if budget==12 else 8 if size=='2b' else 2), task=task, encoding=encoding,
                            token_cap_hits=sum(x['response']['hit_token_cap'] for x in rows), **summarize(rows))
                if budget == 512:
                    item.update(strict_parser_accuracy=statistics.mean(x['strict_score']['correct'] for x in rows),
                                strict_parser_invalid_rate=statistics.mean(not x['strict_score']['valid'] for x in rows))
                e1.append(item)
    for task in protocol['e2']['tasks']:
        cases = baseline.common.read_rows(run/f'{task}_test.jsonl')
        for seed in protocol['e2']['seeds']:
            initial = []
            for arm in ARMS:
                folder = run/f'{task}_{arm}_seed{seed}'
                assert (folder/'COMPLETE.json').exists()
                training = read(folder/'training.json')
                assert training['updates'] == 180
                assert len(training['history']) == 3 and all(x['rows'] == 960 for x in training['history'])
                cfg=protocol['e2']['arms'][arm]
                assert training['semantic_weight']==cfg['semantic_weight']
                assert training['input_mode']==('rule' if cfg['rule_input'] else 'no_rule')
                parameter_counts.add(training['trainable_parameters'])
                initialization=read(folder/'initialization.json')['lora_sha256']
                assert training['initialization_sha256']==initialization
                initial.append(initialization)
                inputs.extend((folder/'training.json', folder/'initialization.json', folder/'COMPLETE.json'))
                for filename, evaluation in (('predictions.jsonl', 'arm_input'),
                                             ('common_rule_predictions.jsonl', 'common_rule')):
                    path = folder/filename
                    if not path.exists():
                        assert evaluation == 'common_rule' and arm.endswith('_rule') and 'no_rule' not in arm
                        continue
                    inputs.append(path)
                    records = baseline.common.read_rows(path)
                    assert [x['id'] for x in records] == [x['id'] for x in cases]
                    for case, row in zip(cases, records):
                        assert baseline.common.parse_answer(row['response']['text'], case['labels']) == row['prediction']
                        assert all(row[k] == v for k, v in baseline.score(case, row['prediction']).items())
                    for encoding in sorted({x['encoding'] for x in records}):
                        group = [x for x in records if x['encoding'] == encoding]
                        for duration in [None] + sorted({x['duration_ms'] for x in group}):
                            subset = group if duration is None else [x for x in group if x['duration_ms'] == duration]
                            item = dict(task=task, encoding=encoding, duration_ms=duration,
                                arm=arm, seed=seed, evaluation=evaluation, **summarize(subset))
                            if duration is None:
                                item['rule_pair_accuracy'] = baseline.metrics(subset)['rule_pair_accuracy']
                            e2.append(item)
            assert len(set(initial)) == 1, (task, seed)
    assert len(parameter_counts)==1,parameter_counts
    return e1, e2, inputs


def means(e2):
    groups = defaultdict(list)
    for row in e2:
        groups[tuple(row[k] for k in ('task','encoding','duration_ms','arm','evaluation'))].append(row)
    result = []
    for key, rows in groups.items():
        assert sorted(x['seed'] for x in rows) == [17, 42, 123]
        item = dict(zip(('task','encoding','duration_ms','arm','evaluation'), key), predictions=sum(x['rows'] for x in rows))
        for metric in ('accuracy','violation_rate','invalid_rate','rule_pair_accuracy'):
            if metric in rows[0]:
                item[metric] = statistics.mean(x[metric] for x in rows)
                item[metric+'_seed_sd'] = statistics.stdev(x[metric] for x in rows)
        result.append(item)
    return result


def contrasts(e2):
    result = []
    for task, encoding in GROUPS:
        for rule in ('no_rule','rule'):
            for evaluation in ('arm_input','common_rule'):
                if rule == 'rule' and evaluation == 'common_rule':
                    continue
                rows = [x for x in e2 if (x['task'],x['encoding']) == (task,encoding)
                        and x['duration_ms'] is None and x['evaluation'] == evaluation]
                ce = {x['seed']: x for x in rows if x['arm'] == 'ce_'+rule}
                sem = {x['seed']: x for x in rows if x['arm'] == 'semantic_'+rule}
                differences = {k:[100*(sem[s][k]-ce[s][k]) for s in (42,17,123)]
                               for k in ('accuracy','violation_rate','rule_pair_accuracy')}
                result.append(dict(task=task, encoding=encoding, rule=rule, evaluation=evaluation,
                    seed_order=[42,17,123], per_seed_difference_pp=differences,
                    mean_difference_pp={k:statistics.mean(v) for k,v in differences.items()}))
    return result


def figures(out, e1, e2):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.size':8,'pdf.fonttype':42,'ps.fonttype':42})
    colors = ('#8998a5','#ab7942','#337da5','#218b67')
    for common_rule in (False,True):
        fig, axes = plt.subplots(2,3,figsize=(7.2,5.2),sharey='row',layout='constrained')
        for col, ((task,encoding), title) in enumerate(zip(GROUPS,GROUP_NAMES)):
            for row,metric in enumerate(('accuracy','violation_rate')):
                ax = axes[row,col]
                for i,arm in enumerate(ARMS):
                    evaluation='common_rule' if common_rule and 'no_rule' in arm else 'arm_input'
                    values = [100*x[metric] for x in e2 if (x['task'],x['encoding'],x['arm'],x['evaluation'],x['duration_ms'])
                              == (task,encoding,arm,evaluation,None)]
                    ax.bar(i,statistics.mean(values),color=colors[i],width=.65)
                    ax.scatter(np.arange(3)*.12+i-.12,values,color='#172733',s=18,zorder=3)
                ax.set_xticks(range(4),['CE\nno rule','CE + SL\nno rule','CE\nCNL','CE + SL\nCNL'],fontsize=6.5)
                ax.set_ylim(0,104); ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
                if row==0: ax.set_title(title,fontsize=9)
                if col==0: ax.set_ylabel(('Accuracy (%)','Violation rate (%)')[row])
        detail=('All models receive CNL at evaluation; labels show training inputs' if common_rule
                else 'Each model receives its training input type at evaluation')
        fig.suptitle('E2: CE and semantic loss (SL, weight 1); bars: means, dots: seeds\n'+detail,fontsize=8.5)
        stem='common_rule_comparison' if common_rule else 'semantic_loss_comparison'
        for suffix in ('pdf','png'): fig.savefig(out/f'{stem}.{suffix}',dpi=180)
        plt.close(fig)
    order = list(dict.fromkeys((x['task'],x['encoding']) for x in e1))
    names = ['Temporal','Speed','Clearance','Entry delay','Stopping','Lane change','Hold: max','Hold: XY']
    assert len(order)==len(names)
    fig,axes=plt.subplots(2,2,figsize=(7.2,5.6),sharey=True,layout='constrained')
    for col,size in enumerate(('2b','8b')):
        for row,metric in enumerate(('accuracy','failure')):
            ax=axes[row,col]
            for j,budget in enumerate((12,512)):
                values=[]
                for task,encoding in order:
                    item=next(x for x in e1 if (x['model'],x['max_new_tokens'],x['task'],x['encoding'])==(size,budget,task,encoding))
                    values.append(100*(item['accuracy'] if metric=='accuracy' else item['violation_rate']+item['invalid_rate']))
                ax.bar(np.arange(8)+(j-.5)*.36,values,width=.36,label=f'{budget} tokens'+(' (post-hoc)' if budget==512 else ' (primary)'),color=('#98aab8','#367a9a')[j])
            ax.set_xticks(range(8),names,rotation=45,ha='right',fontsize=6.5)
            ax.set_ylim(0,105);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
            if row==0:ax.set_title('Pretrained Qwen3-VL-'+size.upper());ax.legend(fontsize=6.5)
            if col==0:ax.set_ylabel(('Accuracy (%)','Violation or invalid output (%)')[row])
    fig.suptitle('E1: unchanged inputs; output budget and answer-parsing sensitivity',fontsize=9)
    for suffix in ('pdf','png'):fig.savefig(out/f'pretrained_vlm_comparison.{suffix}',dpi=180)
    plt.close(fig)


def build(run, out):
    assert not out.exists(), 'Refuse to overwrite an analysis run'
    e1,e2,inputs=audit(run)
    averages=means(e2);effects=contrasts(e2)
    out.mkdir(parents=True)
    baseline.write_json(out/'RESULT.json',dict(project_id='guardsynth-coc',task_id='vlm-constraint-baseline-analysis',
        status='COMPLETE',pretrained=e1,training_per_seed=e2,training_means=averages,semantic_effects=effects))
    figures(out,e1,e2)
    lines=['# VLM 크기와 semantic loss 비교 결과','',
        'E1은 추가 학습 없는 Qwen3-VL 2B·8B 평가, E2는 규칙 유무 × semantic loss 유무의 네 조건을 같은 2B 초기 모델에서 새로 학습한 비교다.',
        'E2: 과제당 960행, 3 epochs, 180 updates, 시드 42·17·123, 총 24회 학습. 테스트는 temporal 240행, 위치 유지 256행(최대 거리/XY 각 128행)이다.', '',
        '## E2: 네 학습 조건','',
        '평균 ± 시드 간 표준편차(%p). 각 점수는 두 유지/대기 시간을 함께 포함한다. 위반율은 전체 예측이 분모이며 답 추출 실패율을 별도로 표시한다. 쌍 정확도는 같은 장면·후보에 서로 다른 규칙을 적용한 두 문항을 모두 맞힌 비율이다.', '',
        '| 과제·표현 | 조건 | 정확도 | 위반율 | 답 추출 실패 | 쌍 정확도 |',
        '|---|---|---:|---:|---:|---:|']
    for (task,encoding),name in zip(GROUPS,GROUP_NAMES):
        for arm,label in zip(ARMS,ARM_NAMES):
            x=next(x for x in averages if (x['task'],x['encoding'],x['arm'],x['evaluation'],x['duration_ms'])==(task,encoding,arm,'arm_input',None))
            cells=[f"{100*x[k]:.2f} ± {100*x[k+'_seed_sd']:.2f}" for k in ('accuracy','violation_rate')]
            lines.append(f"| {name} | {label} | {' | '.join(cells)} | {100*x['invalid_rate']:.2f}% | {100*x['rule_pair_accuracy']:.2f}% |")
    lines += ['', '규칙을 제공한 CE 조건과 CE + semantic 조건의 직접 비교:', '']
    for (task,encoding),name in zip(GROUPS,GROUP_NAMES):
        rows=[x for x in averages if (x['task'],x['encoding'],x['evaluation'],x['duration_ms'])==(task,encoding,'arm_input',None)]
        ce=next(x for x in rows if x['arm']=='ce_rule')
        sem=next(x for x in rows if x['arm']=='semantic_rule')
        lines.append(f"- {name}: 정확도 {100*ce['accuracy']:.2f}% → {100*sem['accuracy']:.2f}%, 위반율 {100*ce['violation_rate']:.2f}% → {100*sem['violation_rate']:.2f}%.")
    lines += ['', '## E2: 동일 입력에서 semantic loss의 추가 효과','',
        '각 시드에서 semantic 조건 − CE 조건을 구한 뒤 평균했다. 정확도 증가는 양수, 위반율 감소는 음수다. 학습 입력의 규칙 유무를 고정한 비교다.', '',
        '| 과제·표현 | 규칙 | 정확도 차이(%p) | 위반율 차이(%p) |', '|---|---|---:|---:|']
    for x in effects:
        if x['evaluation']=='arm_input':
            lines.append(f"| {x['task']} / {x['encoding']} | {x['rule']} | {x['mean_difference_pp']['accuracy']:+.2f} | {x['mean_difference_pp']['violation_rate']:+.2f} |")
    lines += ['', '## E2: 2초 위치 유지','', '| 표현 | 조건 | 정확도 | 위반율 | 예측 수 |','|---|---|---:|---:|---:|']
    for x in averages:
        if x['task']=='position_hold' and x['duration_ms']==2000 and x['evaluation']=='arm_input':
            lines.append(f"| {x['encoding']} | {x['arm']} | {100*x['accuracy']:.2f}% | {100*x['violation_rate']:.2f}% | {x['predictions']} |")
    lines += ['', '## E2: 모든 모델에 평가 때 같은 CNL 제공','',
        '위 네 조건의 주 평가와 분리한 보조 검사다. 규칙 없이 학습한 어댑터에는 평가 입력만 바꾸며 재학습하지 않았다. CNL과 함께 학습한 두 조건은 주 평가의 같은 예측을 재사용한다. 따라서 이 표에서는 평가 정보가 같고 학습 입력과 손실만 다르다.', '',
        '| 과제·표현 | 학습 조건 | 정확도 | 위반율 |', '|---|---|---:|---:|']
    for (task,encoding),name in zip(GROUPS,GROUP_NAMES):
        for arm,label in zip(ARMS,ARM_NAMES):
            evaluation='common_rule' if 'no_rule' in arm else 'arm_input'
            x=next(x for x in averages if (x['task'],x['encoding'],x['arm'],x['evaluation'],x['duration_ms'])==(task,encoding,arm,evaluation,None))
            lines.append(f"| {name} | {label} | {100*x['accuracy']:.2f}% | {100*x['violation_rate']:.2f}% |")
    lines += ['', '## E1: 학습 없는 모델의 출력 한도별 결과','',
        '12토큰은 사전에 고정한 주 평가다. 설명 출력이 잘리는 현상을 확인한 뒤 512토큰과 최종 답 추출을 추가한 결과는 사후 보조 평가다. 입력·이미지는 동일하다. 두 결과를 함께 보고하며 좋은 값으로 대체하지 않는다. 주 평가 배치는 두 모델 모두 4이며, 보조 평가는 8B 배치 2, 2B 배치 8이다. 전처리·생성 병목으로 2B 배치를 변경한 뒤 전체 입력을 다시 실행했으며, 앞선 배치 2의 부분 결과는 집계하지 않았다. 모델 간 실행 속도는 비교하지 않는다.', '',
        '| 모델 | 출력 한도 | 과제·표현 | 정확도 | 위반율 | 답 추출 실패 | 한도 도달/전체 |',
        '|---|---:|---|---:|---:|---:|---:|']
    for x in e1:
        lines.append(f"| {x['model']} | {x['max_new_tokens']} | {x['task']} / {x['encoding']} | {100*x['accuracy']:.2f}% | {100*x['violation_rate']:.2f}% | {100*x['invalid_rate']:.2f}% | {x['token_cap_hits']}/{x['rows']} |")
    lines += ['', '답을 추출할 수 없는 출력은 허용 행동으로 처리하지 않는다. 특히 답 추출 실패율 100%와 관측 위반율 0%의 조합은 준수 성공이 아니다. 한도에 도달한 텍스트에서 추출된 레이블도 완결된 최종 응답과 구분해야 한다. 긴 설명으로 출력 한도에 걸린 점수는 규칙 추론 능력만의 측정이 아니다. 512토큰 결과의 기존 엄격 파서 점수도 RESULT.json에 보존했다.', '',
        '## 해석과 범위','',
        '규칙 없이 평가하는 조건에서 동일 입력의 정답 식별 상한은 temporal 50%, 위치 유지 75%다. 손실에 허용 후보를 알려주더라도, 평가 입력에 없는 사례별 규칙을 복원할 수는 없다. 낮은 위반율과 높은 정답률은 별개이므로 쌍 정확도도 함께 본다. 2초 사례에서 엄격한 유지 후보만 고르면 잘 맞힐 수 있어도, 0.5초 사례와의 적절한 구별은 별도로 확인해야 한다.', '',
        '두 과제 모두 사전학습 모델에서 fresh LoRA를 시작했다. 과거 temporal 어댑터를 이어 학습한 위치 유지 결과와 초기화 이력이 달라 숫자를 직접적인 향상/저하로 해석하지 않는다.', '',
        'Semantic loss는 허용 레이블의 A–D 조건부 확률 합에 적용한 범주형 방식이다. 가중치 1을 실행 전에 고정했으며 이 결과로 다른 가중치를 탐색하지 않았다. 추론 때 후보를 제거하거나 SMT로 출력을 교정하지 않았다. 조건부 손실은 임의 출력이나 실제 차량의 안전을 보장하지 않는다.', '',
        '본 결과는 고정된 합성 후보 선택 입력의 평가다. Alpamayo·nuScenes 사전 진단의 궤적 생성 실험과는 별개다. 새로운 실제 도로 장면이나 궤적 생성 모델의 개선을 입증하지 않으며, 큰 VLM의 성공/실패를 학습의 보편적 필요성으로 일반화하지 않는다.', '',
        'E1은 과제 형식에 대한 추가 학습이 없는 zero-shot 비교이므로, 학습 모델과의 차이에는 과제 적응 효과도 포함된다. 동일 입력과 학습 예산에서 손실의 추가 효과를 분리한 비교는 E2다.', '',
        '실행 세션 중단으로 모델 저장 전 종료된 여섯 학습은 같은 초기 모델과 시드에서 처음부터 재실행했다. 중단된 시도의 로그와 진행 기록은 보존했으며, 완료된 24개 학습만 집계했다. 초기화 일치와 각 학습의 180회 업데이트를 다시 확인했다. 학습을 마치고 저장된 temporal 어댑터 하나는 재학습 없이 평가를 이어갔으며, 2B 보조 추론도 완료된 배치 다음부터 같은 배치 크기로 재개했다.', '',
        'Semantic loss 원문: https://proceedings.mlr.press/v80/xu18h.html',
        '8B 모델 카드: https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct','',
        '[E2 조건별 입력 그래프](semantic_loss_comparison.pdf) · [E2 동일 CNL 평가 그래프](common_rule_comparison.pdf) · [E1 출력 한도 비교](pretrained_vlm_comparison.pdf)','']
    (out/'REPORT_KO.md').write_text('\n'.join(lines))
    inputs += [run/'protocol.json',run/'RESULT.json',run/'RUN_MANIFEST.json',run/'generation_budget_diagnostic/protocol.json',
               run/'pretrained_test.jsonl',run/'temporal_train.jsonl',run/'temporal_test.jsonl',
               run/'position_hold_train.jsonl',run/'position_hold_test.jsonl',Path(__file__),
               Path(baseline.__file__),Path(generation.__file__),Path(batched.__file__),Path(recovery.__file__),
               run/'interrupted_attempts.json',run/'scheduling.json',run/'execution_recovery.json']
    baseline.write_json(out/'RUN_MANIFEST.json',dict(project_id='guardsynth-coc',task_id='vlm-constraint-baseline-analysis',
        run_id=out.name,status='COMPLETE',created_at=datetime.now(timezone.utc).isoformat(),
        inputs=[str(p.relative_to(baseline.ROOT)) for p in inputs],
        input_hashes={str(p.relative_to(baseline.ROOT)):baseline.digest(p) for p in inputs},
        output_hashes={p.name:baseline.digest(p) for p in out.iterdir() if p.is_file()}))
    print(out,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'vlm-constraint-baselines-\d{4}-\d{2}-\d{2}-\d{3}',args.run_id):
        parser.error('Invalid run ID')
    build(baseline.BASE/args.run_id,baseline.BASE/'vlm-constraint-baseline-analysis-2026-10-12-001')
