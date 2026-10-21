"""Plot frozen position-hold before/after results for the English manuscript."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[4]
INPUT = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-position-hold-training-001/position-hold-training-2026-10-08-001/comparison_metrics.csv'
OUTPUT = ROOT / 'projects/04-guardsynth-coc/paper/ieee-access/figures/position-hold-learning-en.pdf'
CONDITIONS = [('interval_maxima', '500', 'Interval maxima: 0.5 s'),
              ('interval_maxima', '2000', 'Interval maxima: 2.0 s'),
              ('xy_waypoints', '500', 'XY waypoints: 0.5 s'),
              ('xy_waypoints', '2000', 'XY waypoints: 2.0 s')]


def main():
    with INPUT.open() as stream:
        records = {(r['phase'], r['encoding'], r['hold_ms'], r['arm']): r
                   for r in csv.DictReader(stream)}
    plt.rcParams.update({'font.size': 8, 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.5), sharey='row')
    plotted = 0
    for column, (encoding, hold, title) in enumerate(CONDITIONS):
        for row, (metric, label, limit) in enumerate([
                ('correct', 'Accuracy (%)', 108),
                ('violations', 'Violation rate (%)', 73)]):
            ax = axes[row, column]
            for phase, offset, color in [('before_test', -.18, '#a8afb7'),
                                         ('after_test', .18, '#267b99')]:
                values = []
                for arm in ['p0', 'p1', 'p2']:
                    record = records[(phase, encoding, hold, arm)]
                    assert int(record['predictions']) == 192
                    values.append(100 * int(record[metric]) / 192)
                    plotted += 1
                bars = ax.bar([i + offset for i in range(3)], values,
                              width=.31, color=color, zorder=3)
                for bar, value in zip(bars, values):
                    ax.text(bar.get_x() + bar.get_width()/2, value + 1.4,
                            f'{value:.1f}' if value else '0',
                            ha='center', va='bottom', fontsize=6.5)
            ax.set_xticks(range(3), ['P0', 'P1', 'P2'])
            ax.set_ylim(0, limit)
            ax.set_yticks([0, 50, 100] if row == 0 else [0, 20, 40, 60])
            ax.tick_params(length=2, labelsize=7)
            ax.grid(axis='y', alpha=.22, zorder=0)
            if row == 0:
                ax.set_title(title, fontsize=8, pad=5)
            if column == 0:
                ax.set_ylabel(label, fontsize=8)
    assert plotted == 48  # 12 strata, two phases, two metrics.
    fig.legend(handles=[Patch(color='#a8afb7', label='Before additional training'),
                        Patch(color='#267b99', label='After additional training')],
               loc='upper center', bbox_to_anchor=(.52, 1.0), ncol=2,
               frameon=False, fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, .93], w_pad=.55, h_pad=.65)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches='tight', pad_inches=.03)
    fig.savefig(OUTPUT.with_suffix('.png'), dpi=180,
                bbox_inches='tight', pad_inches=.03)
    plt.close(fig)
    print(f'{OUTPUT}: 48 values computed from frozen counts; source unchanged')


if __name__ == '__main__':
    main()
