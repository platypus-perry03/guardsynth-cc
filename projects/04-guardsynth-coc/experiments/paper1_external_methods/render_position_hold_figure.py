"""Reformat a frozen position-hold result without altering predictions or metrics."""
from pathlib import Path
import json

import numpy as np
import run_position_hold as r


def main():
    source = r.RUN
    output = source.parent / 'position-hold-figure-2026-10-08-001'
    output.mkdir(exist_ok=False, mode=0o700)
    checksums = json.loads((source / 'report_checksums.json').read_text())
    for relative, expected in checksums.items():
        assert r.digest(source / relative) == expected
    manifest = json.loads((source / 'RUN_MANIFEST.json').read_text())
    assert json.loads((source / 'RESULT.json').read_text())['status'] == 'COMPLETE'
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), constrained_layout=True)
    times = np.arange(1, 65)*.1
    colors = {'native':'#777777', 'low':'#c43b36', 'high':'#2072b8', 'neutral':'#439647'}
    for col, scene in enumerate(manifest['cases']):
        records = [json.loads((source / scene / f'seed_{seed}.json').read_text()) for seed in r.SEEDS]
        for row, route in enumerate(('user', 'coc')):
            ax = axes[row, col]
            ymax = .3
            for level in ('native', 'low', 'high', 'neutral'):
                condition = level if level == 'native' else route+'_'+level
                values = np.array([d['conditions'][condition]['assessments']['low']['radial_displacement_m'] for d in records])
                ymax = max(ymax, float(values[:, :22].max())*1.07)
                label = {'low':'0.5s hold', 'high':'2.0s hold'}.get(level, level)
                ax.plot(times, values.mean(axis=0), color=colors[level], label=label)
                ax.fill_between(times, values.min(axis=0), values.max(axis=0), color=colors[level], alpha=.1)
            ax.axhline(.2, linestyle='--', color='#333333', label='0.2m hold radius')
            ax.axvline(.5, linestyle=':', color=colors['low'])
            ax.axvline(2., linestyle=':', color=colors['high'])
            ax.set(title=('PhysicalAI' if scene == 'physicalai' else 'nuScenes')+': '+('user instruction' if route == 'user' else 'forced CoC addition'),
                   xlabel='Prediction time (s)', ylabel='XY displacement (m)', xlim=(0, 2.2), ylim=(0, ymax))
            ax.grid(alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=5, frameon=False)
    fig.suptitle('Alpamayo R1: position-hold duration compliance\nDistance from decision-time position; three paired action seeds per input', fontsize=12)
    files = []
    for ext in ('pdf', 'png'):
        path = output / f'position_hold_compliance.{ext}'
        fig.savefig(path, dpi=170)
        files.append(path)
    r.write_json(output / 'RUN_MANIFEST.json', dict(project_id='guardsynth-coc', run_id=output.name,
                 source_run=str(source), source_run_checksums=checksums,
                 renderer_sha256=r.digest(Path(__file__)), new_predictions=0,
                 scope='Layout-only rendering of frozen measurements; shorter axis labels'))
    (output / 'REPORT_KO.md').write_text('# 정지 유지 결과 그래프 조판\n\n보존된 48개 출력의 수치를 그대로 사용하고 긴 세로축 제목의 겹침을 해결했다. XY displacement는 결정 시점의 현재 위치에서 떨어진 수평 거리를 뜻한다. 새 예측이나 수치 재평가는 없다.\n')
    r.write_json(output / 'RESULT.json', dict(project_id='guardsynth-coc', status='RENDERED_PENDING_VISUAL_REVIEW',
                 source_run=str(source), new_predictions=0, numeric_values_unchanged=True,
                 outputs={p.name:r.digest(p) for p in files}))
    print(output)


if __name__ == '__main__':
    main()
