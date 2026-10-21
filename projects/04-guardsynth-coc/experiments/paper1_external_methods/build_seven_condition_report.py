"""Validate and report seven conditions with supplied rules at evaluation."""
import argparse
import csv
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import statistics

import run_p0_supplied_rules as run
import run_reasoning_comparison as r

TASKS = ['temporal', 'max_speed', 'min_clearance', 'min_entry_delay', 'cruise_stop', 'lane_change']
TASK_NAMES = ['Temporal waiting', 'Maximum speed', 'Obstacle clearance', 'Entry delay', 'Stopping', 'Lane change']
CONDITIONS = ['p0_rule', 'p0_rule_zs', 'p0_rule_ps', 'P1', 'p1_zs', 'p1_ps', 'P2']
NAMES = ['P0 + rule', 'P0 + rule + ZS-CoT', 'P0 + rule + PS', 'P1', 'P1 + ZS-CoT', 'P1 + PS', 'P2']
METRICS = ['accuracy', 'violation_rate', 'pair_accuracy', 'invalid_rate']


def aggregate(root):
    manifest = run.check_sources(root)
    prior = json.loads((run.PRIOR / 'RESULT.json').read_text())
    assert prior['status'] == 'COMPLETE'
    values = {task: {condition: [] for condition in CONDITIONS} for task in TASKS}
    costs, scored, raw_count = {}, 0, 0
    for task in TASKS:
        for condition, method in [('P1', 'P1'), ('p1_zs', 'zero_shot_cot'), ('p1_ps', 'plan_and_solve'), ('P2', 'P2')]:
            values[task][condition] = prior['per_seed'][task][method]
    for family in run.FAMILIES:
        assert json.loads((root / family / 'RESULT.json').read_text())['status'] == 'COMPLETE'
        cases = r.load_cases(family, arm='p1')
        unique = list(reversed(list({c['input_id']: c for c in reversed(cases)}.values())))
        costs[family] = {}
        for seed in r.SEEDS:
            for method, condition in zip(run.METHODS, CONDITIONS[:3]):
                raw = r.read_rows(root / family / f'{method}-seed{seed}.jsonl')
                assert [row['input_id'] for row in raw] == [c['input_id'] for c in unique]
                for row, case in zip(raw, unique):
                    assert row['checkpoint_arm'] == 'p0' and row['input_arm'] == 'p1'
                    assert row['image_sha256'] == case['image_sha256']
                    assert row['model_first_text'] == run.model_text(case, method)
                    if row['answer'] is not None:
                        assert row['model_second_text'] == r.second_text(case, method, row['reason']['text'])
                    else:
                        assert row['model_second_text'] is None
                    tail = row['reason']['text'] if method == 'direct' else (
                        row['answer']['text'] if row['answer'] is not None else r.ps_answer_tail(row['reason']['text']))
                    assert row['prediction'] == r.parse_answer(tail, case['labels'])
                records = {row['input_id']: row for row in raw}
                rows = r.read_rows(root / family / f'{method}-seed{seed}-predictions.jsonl')
                assert [row['id'] for row in rows] == [c['id'] for c in cases]
                for case, row in zip(cases, rows):
                    assert row['input_id'] == case['input_id'] and row['target'] == case['target']
                    assert row['prediction'] == records[case['input_id']]['prediction']
                    for field, expected in r.score(case, row['prediction']).items():
                        assert row[field] == expected
                for task in sorted({c['task'] for c in cases}):
                    values[task][condition].append(dict(seed=seed, **r.summarize([x for x in rows if x['task'] == task])))
                costs[family].setdefault(condition, []).append(dict(seed=seed, unique_inputs=len(raw),
                    total_generated_tokens=sum(x['generated_tokens'] for x in raw),
                    generation_seconds=sum(x['generation_seconds'] for x in raw),
                    reason_cap_hits=sum(x['reason']['hit_token_cap'] for x in raw),
                    reason_label_only=sum(len(x['reason']['text']) < 8 and r.parse_answer(x['reason']['text'],
                                         'AB' if family == 'static' else 'ABCD') != 'INVALID' for x in raw)))
                scored += len(rows)
                raw_count += len(raw)
    assert scored == 4320 and raw_count == 4140
    for family, methods in prior['unique_inference_costs'].items():
        for condition, method in [('p1_zs', 'zero_shot_cot'), ('p1_ps', 'plan_and_solve')]:
            costs[family][condition] = methods[method]
    means = {task: {condition: {metric: statistics.mean(x[metric] for x in seeds) for metric in METRICS}
                   for condition, seeds in methods.items()} for task, methods in values.items()}
    pooled = {}
    for condition in CONDITIONS:
        seeds = []
        for seed in r.SEEDS:
            rows = [next(x for x in values[task][condition] if x['seed'] == seed) for task in TASKS]
            assert sum(x['rows'] for x in rows) == 480
            seeds.append(dict(seed=seed, **{metric: sum(x[metric]*x['pairs' if metric == 'pair_accuracy' else 'rows'] for x in rows)
                / sum(x['pairs' if metric == 'pair_accuracy' else 'rows'] for x in rows) for metric in METRICS}))
        pooled[condition] = dict(mean={metric: statistics.mean(x[metric] for x in seeds) for metric in METRICS}, per_seed=seeds)
    result = dict(status='COMPLETE', project_id='guardsynth-coc', new_scored_predictions=scored,
                  new_raw_generation_records=raw_count, compared_predictions=10080,
                  input_arm='p1', new_checkpoint_arm='p0', conditions=dict(zip(CONDITIONS, NAMES)),
                  per_seed=values, three_seed_means=means, pooled=pooled, unique_inference_costs=costs,
                  claim_limits=manifest['protocol']['interpretation_limits'])
    r.write_json(root / 'RESULT.json', result)
    r.write_json(root / 'validation.json', dict(status='PASS', checked_at=datetime.now(timezone.utc).isoformat(),
        new_predictions_rescored=scored, new_raw_records_verified=raw_count,
        frozen_sources_checked=len(manifest['sources']), prior_outputs_unchanged=True,
        checkpoint_input_separation='P0 adapters with P1 text', no_new_training=True, no_new_human_labels=True))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default=run.DEFAULT_RUN)
    root = r.OUTPUT / parser.parse_args().run_id
    assert not (root / 'RESULT.json').exists(), 'Completed report already exists'
    result = aggregate(root)
    means, pooled, values = result['three_seed_means'], result['pooled'], result['per_seed']
    with (root / 'comparison_metrics.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['task', 'condition', 'seed', 'rows', 'pairs'] + [x + '_pct' for x in METRICS])
        for task in TASKS:
            for condition in CONDITIONS:
                for row in values[task][condition]:
                    writer.writerow([task, condition, row['seed'], row['rows'], row['pairs']] + [100*row[k] for k in METRICS])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 3, figsize=(18, 10), sharey=True)
    y = np.arange(6)*1.55
    colors = ['#9b6b30', '#d19a55', '#e8c79a', '#34658b', '#549fab', '#8b81b8', '#267f4b']
    for ax, metric, title in zip(axes, ['accuracy', 'violation_rate', 'invalid_rate'],
                                ['Accuracy (%)', 'Identified violations (%)', 'Invalid responses (%)']):
        for i, (condition, name, color) in enumerate(zip(CONDITIONS, NAMES, colors)):
            positions = y+(i-3)*.17
            ax.barh(positions, [100*means[t][condition][metric] for t in TASKS], height=.14, color=color, label=name)
            for position, task in zip(positions, TASKS):
                ax.scatter([100*x[metric] for x in values[task][condition]], [position]*3, color='#222222', s=10)
        ax.set_title(title)
        ax.set_yticks(y, TASK_NAMES)
        ax.set_xlim(0, 105 if metric == 'accuracy' else max(5, max(100*x[metric] for t in TASKS for c in CONDITIONS for x in values[t][c])+2))
        ax.grid(axis='x', alpha=.2)
        ax.set_axisbelow(True)
    axes[0].invert_yaxis()
    fig.suptitle('Seven conditions with supplied rules at evaluation', fontsize=16)
    fig.legend(*axes[0].get_legend_handles_labels(), loc='lower center', bbox_to_anchor=(.5, .045), ncol=4, frameon=False)
    fig.text(.5, .012, 'Bars: three-seed means; dots: individual seeds. P0 receives rules only at evaluation; P1/P2 also receive rules during training.\nSynthetic test rows and reference rules are shared. Invalid answers have unknown admissibility.', ha='center', fontsize=10)
    fig.tight_layout(rect=[0, .15, 1, .95])
    fig.savefig(root / 'seven_condition_comparison.pdf')
    fig.savefig(root / 'seven_condition_comparison.png', dpi=160)
    plt.close(fig)

    def row(cells):
        return '<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in cells)+'</tr>'
    headers = '<tr><th>Condition</th><th>Accuracy (%)</th><th>Violations (%)</th><th>Pair accuracy (%)</th><th>Invalid (%)</th></tr>'
    setup = ''.join(row([name, 'Absent' if i < 3 else ('Natural-language rule' if i < 6 else 'EBLC-derived CNL'),
                       'Natural-language rule' if i < 6 else 'EBLC-derived CNL',
                       'ZS-CoT' if i in (1, 4) else ('Basic PS' if i in (2, 5) else 'Direct label')])
                    for i, name in enumerate(NAMES))
    overall = ''.join(row([name]+[f'{100*pooled[c]["mean"][m]:.2f}' for m in METRICS]) for c, name in zip(CONDITIONS, NAMES))
    findings = ('The P0 checkpoint given rules only at evaluation achieved pooled accuracy of '
                f'{100*pooled["p0_rule"]["mean"]["accuracy"]:.2f}% with direct answers, '
                f'{100*pooled["p0_rule_zs"]["mean"]["accuracy"]:.2f}% with ZS-CoT, and '
                f'{100*pooled["p0_rule_ps"]["mean"]["accuracy"]:.2f}% with basic PS. '
                f'Rule-trained P1 achieved {100*pooled["P1"]["mean"]["accuracy"]:.2f}% and CNL-trained P2 '
                f'{100*pooled["P2"]["mean"]["accuracy"]:.2f}%. These are descriptive results for the existing '
                'checkpoints and synthetic task; task-wise results and response behavior qualify this comparison.')
    task_rows = ''.join(row([label, name]+[f'{100*means[t][c][m]:.2f}' for m in METRICS])
                        for t, label in zip(TASKS, TASK_NAMES) for c, name in zip(CONDITIONS, NAMES))
    cost_rows = ''
    for family, methods in result['unique_inference_costs'].items():
        for c, records in methods.items():
            n = sum(x['unique_inputs'] for x in records)
            cost_rows += row([family, NAMES[CONDITIONS.index(c)], n,
                f'{sum(x["total_generated_tokens"] for x in records)/n:.2f}',
                f'{sum(x["generation_seconds"] for x in records):.2f}',
                sum(x['reason_cap_hits'] for x in records), sum(x['reason_label_only'] for x in records)])
    text = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Seven-condition comparison</title>
<style>body{font:16px/1.5 system-ui;max-width:1200px;margin:35px auto;padding:0 20px;color:#172334}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:7px;border-bottom:1px solid #dce1e5;text-align:left}th{background:#edf2f4}img{max-width:100%}.note{background:#fff5dd;padding:16px}</style>
<h1>Seven conditions with supplied rules at evaluation</h1>
<p>P0 + rule reuses a CoC-only trained P0 checkpoint and supplies the exact frozen P1 natural-language rule at evaluation. Its ZS-CoT and basic PS variants add the same native prompting/extraction procedures used in the completed P1 controls. P1 and its variants use rule-trained P1 checkpoints; P2 uses its own CNL-trained checkpoint and semantically identical rules.</p>
<p>Three existing checkpoint seeds (42, 17, 123), 480 shared test rows per condition/seed: 240 temporal, 144 static, 96 maneuver. Three newly evaluated P0 conditions yield 4,320 additional predictions. Four previous conditions are reused unchanged. Together the table covers 10,080 predictions, not 10,080 independent road scenes. No retraining or human labeling was performed.</p>
<table><tr><th>Condition</th><th>Rule at training</th><th>Rule at evaluation</th><th>Answer procedure</th></tr>'''+setup+'''</table>
<div class="note">P0 + rule versus P1 compares existing checkpoints with different training-time rule exposure, using identical rule-bearing test text. Adding reasoning instructions within an arm measures inference-time prompting. P2 additionally changes the rule representation and checkpoint. These comparisons do not isolate verification causally or reproduce external driving systems. P0 training inputs contained rule-dependent labels without the rule, which limits a pure training-effect interpretation.</div>
<img src="seven_condition_comparison.png" alt="Seven conditions across six tasks">
<h2>Pooled results</h2><p>Row-weighted accuracy, violations and invalid responses; pair-count-weighted pair accuracy; averaged over three seeds.</p>
<table>'''+headers+overall+'''</table><p>'''+findings+'''</p><h2>Task-wise results</h2><table>'''+headers.replace('<th>Condition</th>', '<th>Task</th><th>Condition</th>')+task_rows+'''</table>
<p>Accuracy requires the highest-progress admissible reference label. Identified violations count prohibited selected candidates over all rows. Invalid responses count as accuracy errors and have unknown admissibility. Pair accuracy requires both rule variants to be correct.</p>
<h2>Output behavior and recorded generation cost</h2><table><tr><th>Family</th><th>Condition</th><th>Unique inputs, all seeds</th><th>Mean tokens</th><th>Batch seconds</th><th>First-stage cap hits</th><th>Label-only first stages</th></tr>'''+cost_rows+'''</table>
<p>Direct P0 + rule uses a 12-token answer limit. ZS-CoT and PS use respective 128/256-token reasoning limits and up to 32 answer-extraction tokens. Greedy decoding, batch size 8, bfloat16 and SDPA are fixed. Tokens exclude special tokens; recorded times exclude setup. P1/P2 direct baseline costs were not remeasured. The prior static P1 control was resumed after interruption; times omit unsaved interrupted work. Token limits and truncation differ, so costs are not assumed equal. A label-only first stage does not demonstrate multistep reasoning.</p>
<p>Sources, exact prompts, outputs, predictions, scoring and hashes are archived. The completed four-condition report remains unchanged.</p>
<p><a href="REPORT_KO.md">Korean report</a> · <a href="seven_condition_comparison.pdf">Figure PDF</a> · <a href="comparison_metrics.csv">CSV</a> · <a href="RESULT.json">Detailed metrics</a> · <a href="RUN_MANIFEST.json">Frozen protocol</a> · <a href="validation.json">Validation</a></p></html>'''
    (root / 'comparison_report.html').write_text(text)
    md = '# 규칙 정보를 제공한 일곱 조건 비교\n\n- 소유 프로젝트: `guardsynth-coc`\n- 상태: 완료\n- 새 예측: 4,320개; 기존 네 조건과 합쳐 10,080개 예측 비교\n- 기존 테스트 480행 × 학습 seed 3개 × 조건 7개; 독립 영상 수가 아니다.\n- 새 학습·사람 주석 없음\n\n'
    md += 'P0 + 규칙은 CoC만으로 학습한 P0 체크포인트에 평가 때만 P1의 규칙 포함 입력을 제공한 조건이다. P1은 학습·평가 때 규칙을 제공했고, P2는 같은 규칙을 EBLC 유래 CNL로 제공했다. ZS-CoT와 기본 PS는 각 체크포인트에 추론 지시 및 원래 답 추출 절차만 추가한다.\n\n'
    md += '| 조건 | 정확도 (%) | 확인된 위반율 (%) | 계약 쌍 정확도 (%) | 무효 응답률 (%) |\n|---|---:|---:|---:|---:|\n'
    for c, name in zip(CONDITIONS, NAMES):
        md += '| '+name+' | '+' | '.join(f'{100*pooled[c]["mean"][m]:.2f}' for m in METRICS)+' |\n'
    md += '\nP0 + 규칙과 P1을 비교하면 기존 체크포인트의 규칙 포함 학습과 평가 시 규칙 제공을 구분할 수 있다. 각 계열 내부의 직접 답변과 추론 프롬프트 조건은 추론 지시의 추가 효과를 비교한다. 다만 P0는 학습 당시 규칙 없이 규칙별 정답을 학습했으므로, 이를 일반적인 순수 학습 효과 추정으로 확대할 수 없다. P2는 표현과 체크포인트도 다르며 검증 자체의 인과적 효과는 분리되지 않는다.\n\n'
    md += '원시 응답에서 실제 추론이 생성됐는지 확인해야 한다. 첫 단계가 문자 답만 출력한 경우 다단계 추론을 수행했다고 해석하지 않는다. ZS-CoT/PS의 한도는 128/256토큰, 최종 답 추출은 32토큰, 직접 답변은 12토큰이다. 긴 응답의 잘림과 무효 응답을 별도 보고하며, 무효 응답의 허용 여부는 미확인이다.\n\n'
    md += '| 과제 | 조건 | 평균 생성 토큰 | 첫 단계 한도 도달 / 고유 입력 | 문자만 출력 / 고유 입력 |\n|---|---|---:|---:|---:|\n'
    for family, methods in result['unique_inference_costs'].items():
        for c, records in methods.items():
            n = sum(x['unique_inputs'] for x in records)
            md += f'| {family} | {NAMES[CONDITIONS.index(c)]} | {sum(x["total_generated_tokens"] for x in records)/n:.2f} | {sum(x["reason_cap_hits"] for x in records)}/{n} | {sum(x["reason_label_only"] for x in records)}/{n} |\n'
    md += '\n4,320개 새 예측을 후보 규칙으로 다시 채점하고, 4,140개 원시 생성의 입력·답 추출·예측 연결을 확인했다. 동결 소스와 이전 산출물의 해시를 모두 확인했다. 기동 과제의 중복 입력은 추론 후 원래 평가 행으로 복원했다.\n\n[영어 보고서](comparison_report.html) · [비교 그래프](seven_condition_comparison.pdf) · [과제별 CSV](comparison_metrics.csv) · [상세 결과](RESULT.json) · [검사 기록](validation.json)\n'
    (root / 'REPORT_KO.md').write_text(md)
    outputs = ['RESULT.json', 'validation.json', 'comparison_metrics.csv', 'seven_condition_comparison.pdf',
               'seven_condition_comparison.png', 'comparison_report.html', 'REPORT_KO.md']
    r.write_json(root / 'report_checksums.json', {str(p): r.digest(p) for p in [Path(__file__).resolve()]+[root/name for name in outputs]})
    print(json.dumps({NAMES[i]: {m: round(100*v, 2) for m, v in pooled[c]['mean'].items()} for i,c in enumerate(CONDITIONS)}, indent=2))


if __name__ == '__main__':
    main()
