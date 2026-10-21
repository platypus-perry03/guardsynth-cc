"""Illustrate supplied-input review and source-preserving binding."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = ROOT / 'projects/04-guardsynth-coc/paper/ieee-access/figures/video-grounding-en.pdf'


def main():
    plt.rcParams.update({'font.size': 9, 'pdf.fonttype': 42})
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.set(xlim=(0, 10), ylim=(0, 6.85))
    ax.axis('off')
    blue, orange, green, red = '#285f82', '#976223', '#357354', '#a24f4f'

    def box(x, y, width, height, color, fill):
        ax.add_patch(FancyBboxPatch((x, y), width, height,
                                   boxstyle='round,pad=0.04,rounding_size=.08',
                                   edgecolor=color, facecolor=fill, linewidth=.9))

    def arrow(start, end, color='#4a5964', dashed=False):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>',
                                    mutation_scale=10, linewidth=.9, color=color,
                                    linestyle='--' if dashed else '-'))

    box(2.0, 6.19, 6.0, .47, '#63717d', '#f0f3f5')
    ax.text(5, 6.43, 'Original CoC: action and causal context', ha='center', va='center')
    arrow((2.65, 6.17), (2.2, 5.79), dashed=True)
    arrow((7.35, 6.17), (7.8, 5.79), dashed=True)

    box(.18, 4.46, 4.1, 1.32, blue, '#eaf3f9')
    ax.text(2.23, 5.54, '1. Review supplied observations', ha='center', color=blue, weight='bold')
    ax.text(2.23, 4.99, 'Target, zone, occupancy, event time\nExample: zone cleared at 11.0 s\nVideo segment and observation confidence',
            ha='center', va='center', linespacing=1.5)
    box(5.72, 4.46, 4.1, 1.32, orange, '#fbf3e6')
    ax.text(7.77, 5.54, '2. Review the supplied rule', ha='center', color=orange, weight='bold')
    ax.text(7.77, 4.99, 'Policy, instruction, or confirmed sign\nExample: wait at least 0.5 s after clearance\nRule reference and supplied duration',
            ha='center', va='center', linespacing=1.5)
    arrow((2.23, 4.44), (3.5, 4.01))
    arrow((7.77, 4.44), (6.5, 4.01))

    box(2.77, 2.96, 4.46, 1.02, green, '#edf6ef')
    ax.text(5, 3.75, '3. Human confirmation of applicability', ha='center', color=green, weight='bold')
    ax.text(5, 3.35, 'Same target, zone, and decision time?\nAccept evidence; confirm rule; disclose assumptions',
            ha='center', va='center', fontsize=8.5, linespacing=1.5)
    box(7.98, 2.94, 1.83, 1.04, red, '#fbefef')
    ax.text(8.9, 3.47, 'Unconfirmed\nHold candidate\nNo learning export',
            ha='center', va='center', color=red, fontsize=8, linespacing=1.5)
    arrow((7.26, 3.45), (7.94, 3.45), red, dashed=True)
    arrow((5, 2.94), (5, 2.55), green)
    ax.text(5.13, 2.74, 'Accepted', color=green, va='center', fontsize=8)

    box(2.05, 1.15, 5.9, 1.35, '#4a5964', '#f6f8fa')
    ax.text(5, 2.27, '4. Bind inputs while preserving their sources', ha='center', weight='bold')
    ax.plot([5, 5], [1.30, 2.04], color='#c0c7ce', linewidth=.7)
    ax.text(3.55, 1.69, 'Scene / query binding\nclear_ms = 11000\nVideo evidence reference',
            ha='center', va='center', color=blue, linespacing=1.45)
    ax.text(6.45, 1.69, 'EBLC rule field\nrelease_clear_ms = 500\nRule evidence reference',
            ha='center', va='center', color=orange, linespacing=1.45)
    arrow((5, 1.13), (5, .73))
    box(1.8, .18, 6.4, .53, '#63717d', '#f0f3f5')
    ax.text(5, .45, 'Next: specify EBLC → logical checks → CNL → augment CoC',
            ha='center', va='center', fontsize=9)

    fig.subplots_adjust(left=.01, right=.99, bottom=.01, top=.99)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, bbox_inches='tight', pad_inches=.025)
    fig.savefig(OUTPUT.with_suffix('.png'), dpi=190,
                bbox_inches='tight', pad_inches=.025)
    plt.close(fig)
    print(OUTPUT)


if __name__ == '__main__':
    main()
