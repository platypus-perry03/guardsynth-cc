"""Export the executed supplementary comparison, keeping information limits visible."""
import argparse
import csv
import html
import json
from pathlib import Path
import statistics

from run_reasoning_comparison import OUTPUT, TRIGGERS, digest

METHODS = ['P0', 'zero_shot_cot', 'plan_and_solve', 'P1', 'P2']
NAMES = {'P0':'P0: CoC only', 'zero_shot_cot':'P0 + Zero-shot CoT prompt',
         'plan_and_solve':'P0 + Plan-and-Solve prompt', 'P1':'P1: NL constraint', 'P2':'P2: EBLC-derived CNL'}
TASKS = ['temporal', 'max_speed', 'min_clearance', 'min_entry_delay', 'cruise_stop', 'lane_change']
LABELS = ['Temporal waiting', 'Maximum speed', 'Obstacle clearance', 'Entry delay', 'Stopping', 'Lane change']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='reasoning-comparison-2026-10-07-001')
    args = parser.parse_args()
    folder = OUTPUT / args.run_id
    result = json.loads((folder/'RESULT.json').read_text())
    assert result['status'] == 'COMPLETE' and result['scored_predictions'] == 2880
    means = result['three_seed_means']
    with (folder/'comparison_metrics.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['task','method','seed','rows','pairs','accuracy_pct','violation_pct_all_rows','invalid_pct','pair_accuracy_pct'])
        for task in TASKS:
            for method in METHODS:
                for row in result['per_seed'][task][method]:
                    writer.writerow([task,method,row['seed'],row['rows'],row['pairs'],*[100*row[k] for k in ('accuracy','violation_rate','invalid_rate','pair_accuracy')]])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.size':10, 'axes.spines.top':False, 'axes.spines.right':False})
    fig, axes = plt.subplots(1,2,figsize=(14,8),sharey=True)
    colors = ['#687786','#4798a6','#8076b9','#d8a143','#267f4b']
    y = np.arange(6)*1.35
    for ax,metric,title in zip(axes,['accuracy','violation_rate'],['Accuracy (%) — higher is better','Constraint violations (%) — lower is better']):
        for i,method in enumerate(METHODS):
            values = [100*means[task][method][metric] for task in TASKS]
            positions = y + (i-2)*.19
            ax.barh(positions,values,height=.16,color=colors[i],label=NAMES[method])
            for pos,task,value in zip(positions,TASKS,values):
                seeds = [100*x[metric] for x in result['per_seed'][task][method]]
                ax.scatter(seeds,[pos]*3,s=9,color='#222222',zorder=3)
                ax.text(105 if metric=='accuracy' else 54,pos,f'{value:.1f}',ha='right',va='center',fontsize=7)
        ax.set_title(title,fontsize=12)
        ax.set_xlim(0,106 if metric=='accuracy' else 55)
        ax.set_yticks(y,LABELS)
        ax.grid(axis='x',alpha=.2)
        ax.set_axisbelow(True)
    axes[0].axvline(50,color='#aa3333',linestyle=':',linewidth=1)
    axes[0].invert_yaxis()
    fig.suptitle('Existing P0 checkpoints with two reasoning prompts',fontsize=16,y=.98)
    fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.045),ncol=3,frameon=False)
    fig.text(.5,.012,'Three optimization seeds; dots show individual seeds. P1/P2 receive extra rule information.\nThe 50% line is the fixed-input ceiling for the three conditions without supplied constraints.',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.14,1,.95])
    fig.savefig(folder/'reasoning_comparison.png',dpi=180)
    fig.savefig(folder/'reasoning_comparison.pdf')
    plt.close(fig)
    table_rows = []
    for task,label in zip(TASKS,LABELS):
        for method in METHODS:
            m = means[task][method]
            table_rows.append('<tr>'+''.join(f'<td>{html.escape(x)}</td>' for x in [label,NAMES[method],*[f'{100*m[k]:.2f}' for k in ('accuracy','violation_rate','pair_accuracy','invalid_rate')]])+'</tr>')
    costs = []
    for family,methods in result['unique_inference_costs'].items():
        for method,rows in methods.items():
            count = sum(x['unique_inputs'] for x in rows)
            labels_only = sum(x['reason_label_only'] for x in rows)
            costs.append('<tr>'+''.join(f'<td>{x}</td>' for x in [family,NAMES[method],count,
                f'{statistics.mean(x["mean_generated_tokens"] for x in rows):.2f}',
                f'{sum(x["generation_seconds"] for x in rows):.1f}',f'{100*labels_only/count:.1f}%',sum(x['reason_cap_hits'] for x in rows)])+'</tr>')
    report = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Reasoning-prompt comparison</title>
<style>body{font:16px/1.55 system-ui;max-width:1200px;margin:40px auto;padding:0 20px;color:#172334}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;border-bottom:1px solid #dce1e5;text-align:left}th{background:#edf2f4}img{max-width:100%}.note{background:#fff5dd;padding:18px}code{font-size:13px}a{color:#256f89}</style>
<h1>Reasoning-prompt comparison on the existing P0 checkpoints</h1>
<p>Two supplementary inference controls use the existing Qwen3-VL-2B-Instruct P0 LoRA checkpoints. Zero-shot CoT uses the original step-by-step trigger and two-stage extraction. Basic Plan-and-Solve uses prompt_201 and its conditional extraction procedure. Neither receives an added constraint. There is no additional training or manual labeling.</p>
<p>Each method is scored on 480 primary test rows for each of three optimization seeds (42, 17, 123): 2,880 scored predictions in total. Deterministic outputs are reused for identical image-and-text inputs within the same checkpoint/method. This produces 1,092 unique first-stage inference cases. Archived P0/P1/P2 test predictions provide the reference comparison.</p>
<div class="note"><b>Interpretation boundary.</b> These are transfers of prompting procedures to our VLM task, not reproductions of the original GPT-3 experiments or of DriveLM/DriveVLM. P1/P2 receive rule information that the reasoning controls do not. Every identical P0 input group has conflicting target labels, giving a 50% fixed-output accuracy ceiling. Therefore, the comparison does not establish equal-information algorithm superiority.</div>
<img src="reasoning_comparison.png" alt="Accuracy and constraint violations across six tasks">
<h2>Task results</h2><p>Percentages are means across three seeds. Pair accuracy requires both rule variants to be correct. Invalid answers remain in the accuracy denominator. Violation rate counts identified inadmissible choices across all rows; invalid answers have unknown admissibility and are reported separately.</p>
<table><thead><tr><th>Task</th><th>Condition</th><th>Accuracy</th><th>Violations</th><th>Pair accuracy</th><th>Invalid</th></tr></thead><tbody>''' + ''.join(table_rows) + '''</tbody></table>
<h2>Observed output and inference cost</h2><p>The first-stage output often contains only an option label, despite the reasoning instruction. Such outputs are not evidence of an executed multistep reasoning chain. The short-label column reports first-stage strings shorter than eight characters that contain a valid option. All 48 longer Plan-and-Solve outputs in the static task reached the 256-token reasoning cap before answer extraction. Raw reasoning and final-answer outputs are retained for inspection.</p>
<table><thead><tr><th>Family</th><th>Method</th><th>Unique inputs, all seeds</th><th>Mean generated text tokens</th><th>Batch generation seconds, all seeds</th><th>Short label first stage</th><th>Reasoning cap hits</th></tr></thead><tbody>''' + ''.join(costs) + '''</tbody></table>
<p>Native reasoning caps differ: 128 tokens for Zero-shot CoT and 256 for basic PS; answer extraction has a 32-token cap. Token counts exclude special tokens. Timings are synchronized batch-generation wall time, including both stages and excluding checkpoint setup. They measure local throughput, not single-request latency or cost superiority over archived baselines.</p>
<h2>Reproducibility</h2><p><a href="RUN_MANIFEST.json">Frozen protocol and input hashes</a> · <a href="RESULT.json">Results and per-seed metrics</a> · <a href="comparison_metrics.csv">CSV</a> · <a href="reasoning_comparison.pdf">Figure PDF</a></p>
<p>Method sources: <a href="https://github.com/kojima-takeshi188/zero_shot_cot">Zero-shot CoT official implementation</a> and <a href="https://github.com/AGI-Edgerunners/Plan-and-Solve-Prompting">Plan-and-Solve official implementation</a>; pinned commits are recorded in the manifest.</p></html>'''
    (folder/'comparison_report.html').write_text(report)
    paths = [Path(__file__), folder/'comparison_metrics.csv', folder/'reasoning_comparison.png', folder/'reasoning_comparison.pdf', folder/'comparison_report.html']
    (folder/'report_checksums.json').write_text(json.dumps({str(p):digest(p) for p in paths},indent=2)+'\n')
    print(folder/'comparison_report.html')


if __name__ == '__main__':
    main()
