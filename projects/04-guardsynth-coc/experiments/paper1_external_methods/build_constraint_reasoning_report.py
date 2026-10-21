"""Export the constraint-aware P1 prompting comparison from completed records."""
import argparse
import csv
import html
import json
from pathlib import Path
import statistics

from run_reasoning_comparison import OUTPUT, SEEDS, digest

METHODS = ['P1', 'zero_shot_cot', 'plan_and_solve', 'P2']
NAMES = ['P1', 'P1 + ZS-CoT', 'P1 + PS', 'P2']
TASKS = ['temporal', 'max_speed', 'min_clearance', 'min_entry_delay', 'cruise_stop', 'lane_change']
LABELS = ['Temporal waiting', 'Maximum speed', 'Obstacle clearance', 'Entry delay', 'Stopping', 'Lane change']
METRICS = ['accuracy', 'violation_rate', 'pair_accuracy', 'invalid_rate']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default='constraint-reasoning-2026-10-07-001')
    folder = OUTPUT / parser.parse_args().run_id
    result = json.loads((folder / 'RESULT.json').read_text())
    assert result['status'] == 'COMPLETE' and result['scored_predictions'] == 2880
    assert result['input_arm'] == 'p1'
    per_seed = result['per_seed']
    pooled = {}
    for method in METHODS:
        seed_metrics = []
        for seed in SEEDS:
            rows = [next(x for x in per_seed[task][method] if x['seed'] == seed) for task in TASKS]
            assert sum(x['rows'] for x in rows) == 480
            seed_metrics.append(dict(seed=seed, **{
                metric: sum(x[metric] * x['pairs' if metric == 'pair_accuracy' else 'rows'] for x in rows)
                / sum(x['pairs' if metric == 'pair_accuracy' else 'rows'] for x in rows)
                for metric in METRICS
            }))
        pooled[method] = {'mean': {k: statistics.mean(x[k] for x in seed_metrics) for k in METRICS},
                          'per_seed': seed_metrics}
    (folder / 'summary_metrics.json').write_text(json.dumps(pooled, indent=2) + '\n')
    with (folder / 'comparison_metrics.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['task', 'method', 'seed', 'rows', 'pairs'] + [x + '_pct' for x in METRICS])
        for task in TASKS:
            for method in METHODS:
                for row in per_seed[task][method]:
                    writer.writerow([task, method, row['seed'], row['rows'], row['pairs']] + [100 * row[k] for k in METRICS])

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 3, figsize=(16, 7), sharey=True)
    y = np.arange(6) * 1.1
    colors = ['#d8a143', '#4798a6', '#8076b9', '#267f4b']
    for ax, metric, title in zip(axes, ['accuracy', 'violation_rate', 'invalid_rate'], ['Accuracy (%)', 'Identified violations (%)', 'Invalid responses (%)']):
        for i, (method, name, color) in enumerate(zip(METHODS, NAMES, colors)):
            positions = y + (i - 1.5) * .19
            values = [100 * result['three_seed_means'][task][method][metric] for task in TASKS]
            ax.barh(positions, values, height=.16, color=color, label=name)
            for position, task in zip(positions, TASKS):
                ax.scatter([100 * x[metric] for x in per_seed[task][method]], [position] * 3, s=12, color='#222222')
        ax.set_title(title)
        ax.set_yticks(y, LABELS)
        ax.set_xlim(0, 105 if metric == 'accuracy' else max(5, max(100 * row[metric] for t in TASKS for m in METHODS for row in per_seed[t][m]) + 2))
        ax.grid(axis='x', alpha=.2)
        ax.set_axisbelow(True)
    axes[0].invert_yaxis()
    fig.suptitle('Constraint-aware prompting on existing P1 checkpoints', fontsize=15)
    fig.legend(*axes[0].get_legend_handles_labels(), loc='lower center', bbox_to_anchor=(.5, .055), ncol=4, frameon=False)
    fig.text(.5, .018, 'Three seeds; dots show individual seeds. All conditions receive the supplied rules.\nInvalid responses have unknown admissibility. P1/P2 baselines are archived; prompting controls are newly executed.', ha='center', fontsize=10)
    fig.tight_layout(rect=[0, .16, 1, .94])
    fig.savefig(folder / 'constraint_reasoning_comparison.pdf')
    fig.savefig(folder / 'constraint_reasoning_comparison.png', dpi=180)
    plt.close(fig)

    def table_row(values):
        return '<tr>' + ''.join('<td>' + html.escape(str(x)) + '</td>' for x in values) + '</tr>'
    pooled_rows = ''.join(table_row([name] + [f'{100 * pooled[method]["mean"][k]:.2f}' for k in METRICS]) for method, name in zip(METHODS, NAMES))
    task_rows = ''.join(table_row([label, name] + [f'{100 * result["three_seed_means"][task][method][k]:.2f}' for k in METRICS]) for task, label in zip(TASKS, LABELS) for method, name in zip(METHODS, NAMES))
    cost_rows = ''
    for family, methods in result['unique_inference_costs'].items():
        for method in ['zero_shot_cot', 'plan_and_solve']:
            rows = methods[method]
            count = sum(x['unique_inputs'] for x in rows)
            tokens = sum(x['total_generated_tokens'] for x in rows)
            cost_rows += table_row([family, NAMES[METHODS.index(method)], count, f'{tokens / count:.2f}',
                                   f'{sum(x["generation_seconds"] for x in rows):.2f}',
                                   sum(x['reason_cap_hits'] for x in rows), sum(x['reason_label_only'] for x in rows)])
    headers = '<tr><th>Condition</th><th>Accuracy</th><th>Violations</th><th>Pair accuracy</th><th>Invalid</th></tr>'
    report = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Constraint-aware reasoning comparison</title>
<style>body{font:16px/1.5 system-ui;max-width:1150px;margin:35px auto;padding:0 20px;color:#172334}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;border-bottom:1px solid #dce1e5;text-align:left}th{background:#edf2f4}img{max-width:100%}.note{background:#fff5dd;padding:16px}</style>
<h1>Constraint-aware reasoning on existing P1 checkpoints</h1>
<p>P1 + ZS-CoT adds the original Zero-Shot Chain-of-Thought instruction and two-stage answer extraction. P1 + PS adds the basic Plan-and-Solve instruction and native conditional answer extraction. Both reuse each existing P1 LoRA checkpoint, image, CoC, supplied natural-language rule and candidate descriptions. No new training or labels are created.</p>
<p>Each procedure scores 240 temporal, 144 static and 96 maneuver test rows for each of three seeds (42, 17, 123): 2,880 new predictions. P1 and P2 are archived baselines on the same rows, rule semantics, candidates and references. P2 has its own CNL representation and checkpoint. The two prompt procedures remain transferred adaptations, not original-paper model reproductions.</p>
<div class="note">This comparison tests inference-time prompting given the supplied rules. It does not isolate a causal effect of verification, reproduce DriveLM/DriveVLM, or establish real-road driving safety. The synthetic test images and numeric candidates are unchanged. Native reasoning token caps differ, so inference cost is reported rather than assumed equal.</div>
<p><strong>Observed behavior matters:</strong> all temporal and maneuver first-stage outputs were single candidate labels, despite the reasoning instructions. Static outputs frequently reached the reasoning-token cap: 335/432 ZS-CoT and 323/432 PS generations. Thus the observed scores describe prompting existing label-trained checkpoints under these generation limits; they are not a general ranking of fully realized reasoning methods. P2 does not lead on every task: both prompting controls reached 100% lane-change accuracy, compared with 97.92% for P2.</p>
<img src="constraint_reasoning_comparison.png" alt="Accuracy and violations across six tasks">
<h2>Pooled results (%)</h2><p>Row-weighted results across all 480 test rows, averaged over three seeds; pair accuracy is weighted by the number of pairs.</p>
<table>''' + headers + pooled_rows + '''</table><h2>Task-wise results (%)</h2><table>''' + headers.replace('<th>Condition</th>', '<th>Task</th><th>Condition</th>') + task_rows + '''</table>
<p>Accuracy compares the selected label with the highest-progress admissible reference. Violations count identified prohibited choices over all rows. Invalid responses retain their place in the accuracy denominator; their admissibility is unknown and their rate is reported separately. Pair accuracy requires both supplied-rule variants to be correct.</p>
<h2>Observed generation and cost</h2><table><tr><th>Family</th><th>Condition</th><th>Unique inputs, all seeds</th><th>Mean generated tokens</th><th>Batch generation seconds</th><th>Reasoning cap hits</th><th>Short-label first stages</th></tr>''' + cost_rows + '''</table>
<p>ZS-CoT uses up to 128 reasoning tokens and PS up to 256; final answer extraction uses up to 32. Text-token counts exclude special tokens. Timings are synchronized batch-generation wall time, including both stages, excluding model setup; baseline timing was not remeasured. A requested reasoning chain is not proof that a label-trained checkpoint performs multistep reasoning; raw outputs are retained.</p>
<p>The static worker stopped when the user interrupted the turn. Its saved outputs were preserved; the final 64 unique inputs were resumed with unchanged checkpoint, prompts and token limits. Reported generation times cover recorded completed batches and exclude any interrupted work that was not saved. A continuous full static-worker wall time is unavailable. See the <a href="resume_manifest.json">resume record</a> and <a href="validation.json">record validation</a>.</p>
<p><a href="RUN_MANIFEST.json">Protocol and hashes</a> · <a href="RESULT.json">Task/seed records</a> · <a href="summary_metrics.json">Pooled metrics</a> · <a href="comparison_metrics.csv">CSV</a> · <a href="constraint_reasoning_comparison.pdf">Figure PDF</a></p></html>'''
    (folder / 'comparison_report.html').write_text(report)
    outputs = ['summary_metrics.json', 'comparison_metrics.csv', 'constraint_reasoning_comparison.pdf', 'constraint_reasoning_comparison.png', 'comparison_report.html']
    (folder / 'report_checksums.json').write_text(json.dumps({str(p): digest(p) for p in [Path(__file__)] + [folder / name for name in outputs]}, indent=2) + '\n')
    print(json.dumps({method: {k: round(v * 100, 2) for k, v in data['mean'].items()} for method, data in pooled.items()}, indent=2))


if __name__ == '__main__':
    main()
