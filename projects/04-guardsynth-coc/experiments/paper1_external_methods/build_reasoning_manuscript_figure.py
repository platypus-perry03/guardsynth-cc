"""Render the archived reasoning comparison at the manuscript's physical width."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-reasoning-comparison-001/reasoning-comparison-2026-10-07-001/RESULT.json'
OUTPUT = ROOT / 'projects/04-guardsynth-coc/paper/ieee-access/figures/reasoning-comparison-en.pdf'
METHODS = ['P0', 'zero_shot_cot', 'plan_and_solve', 'P1', 'P2']
NAMES = ['P0', 'P0 + ZS-CoT', 'P0 + PS', 'P1', 'P2']
TASKS = ['temporal', 'max_speed', 'min_clearance', 'min_entry_delay', 'cruise_stop', 'lane_change']
LABELS = ['Temporal wait', 'Max. speed', 'Min. clearance', 'Entry delay', 'Stopping', 'Lane change']
COLORS = ['#687786', '#4798a6', '#8076b9', '#d8a143', '#267f4b']


def main():
    data = json.loads(INPUT.read_text())
    assert data['status'] == 'COMPLETE' and data['scored_predictions'] == 2880
    plt.rcParams.update({'font.size':9, 'pdf.fonttype':42,
                         'axes.spines.top':False, 'axes.spines.right':False})
    fig, axes = plt.subplots(1,2,figsize=(7.2,3.0),sharey=True)
    y = np.arange(6)*1.35
    for ax, metric, title in zip(axes,['accuracy','violation_rate'],['(a) Accuracy (%)','(b) Violation rate (%)']):
        for i, method in enumerate(METHODS):
            values = [100*data['three_seed_means'][task][method][metric] for task in TASKS]
            positions = y+(i-2)*.19
            ax.barh(positions,values,height=.16,color=COLORS[i],label=NAMES[i])
            for pos,task in zip(positions,TASKS):
                seed_values = [100*row[metric] for row in data['per_seed'][task][method]]
                ax.scatter(seed_values,[pos]*3,s=5,color='#222222',zorder=3)
        ax.set_title(title,fontsize=10)
        ax.set_xlim(0,104 if metric=='accuracy' else 52)
        ax.set_xticks([0,50,100] if metric=='accuracy' else [0,25,50])
        ax.set_yticks(y,LABELS)
        ax.tick_params(length=2)
        ax.grid(axis='x',alpha=.2)
        ax.set_axisbelow(True)
    axes[0].axvline(50,color='#aa3333',linestyle=':',linewidth=.9)
    axes[0].invert_yaxis()
    fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.01),ncol=5,frameon=False,columnspacing=1.2,handlelength=1.2)
    fig.tight_layout(rect=[0,.055,1,1],w_pad=1)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(OUTPUT)
    plt.close(fig)
    print(OUTPUT)


if __name__ == '__main__':
    main()
