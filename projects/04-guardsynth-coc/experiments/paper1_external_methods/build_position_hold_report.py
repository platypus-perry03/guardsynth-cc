"""Replay position-hold compliance and plot paired waiting-duration interventions."""
import csv
import json
import math

import numpy as np
import run_position_hold as r


def main():
    root = r.RUN
    assert not (root / 'RESULT.json').exists(), 'Completed reports cannot be overwritten'
    manifest = json.loads((root / 'RUN_MANIFEST.json').read_text())
    for path, expected in manifest['source_hashes'].items():
        assert r.digest(path) == expected
    from alpamayo_r1.config import AlpamayoR1Config
    from transformers import AutoTokenizer
    config = AlpamayoR1Config.from_pretrained(r.MODEL, revision=r.MODEL_REV, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(config.vlm_name_or_path, local_files_only=True)
    rows, pairs, token_counts, saved = [], [], {}, {}
    replay_error = 0.
    for scene, case in manifest['cases'].items():
        folder = root / scene
        assert json.loads((folder / 'RESULT.json').read_text())['status'] == 'COMPLETE'
        source_input = r.input_path(case, folder)
        assert r.digest(source_input) == case['input_sha256']
        assert r.digest(r.Path(case['parent_run']) / 'RUN_MANIFEST.json') == case['parent_manifest_sha256']
        data = r.torch.load(source_input, weights_only=True)
        origin = data['ego_history_xyz'][0, 0, -1].numpy()
        saved[scene] = []
        for seed in r.SEEDS:
            path = folder / f'seed_{seed}.json'
            d = json.loads(path.read_text())
            arrays = np.load(path.with_suffix('.npz'))
            assert r.digest(path.with_suffix('.npz')) == d['trajectories_sha256']
            assert np.array_equal(arrays['native'], arrays['self_splice'])
            saved[scene].append(d)
            counts = {c: len(tokenizer.encode(d['conditions'][c]['added_text'], add_special_tokens=False))
                      for c in ('user_low', 'user_high', 'user_neutral')}
            assert counts['user_low'] == counts['user_high']
            token_counts[scene] = counts
            for condition, record in d['conditions'].items():
                scalar = [math.hypot(float(p[0])-float(origin[0]), float(p[1])-float(origin[1]))
                          for p in arrays[condition]]
                for level, wait in (('low', case['lower_wait_s']), ('high', case['upper_wait_s'])):
                    metrics = r.trajectory_metrics(arrays[condition], origin, wait)
                    assert metrics == record['assessments'][level]
                    replay_error = max(replay_error, max(abs(x-y) for x, y in zip(scalar, metrics['radial_displacement_m'])))
                    assert replay_error < 1e-5
                    count = int(round(wait / .1))
                    assert any(x > .21 for x in scalar[:count]) == metrics['exceeds_with_0_01_m_tolerance']
                    departures = [i for i, x in enumerate(scalar) if x > .21]
                    assert metrics['first_departure_sample_s'] == ((departures[0]+1)*.1 if departures else None)
                    row = dict(dataset=scene, seed=seed, condition=condition, assessed_wait=level,
                               rule_supplied=condition.endswith('_'+level), **metrics)
                    del row['radial_displacement_m']
                    rows.append(row)
            for route in ('user', 'coc'):
                low = d['conditions'][route+'_low']['assessments']['low']
                high = d['conditions'][route+'_high']['assessments']['high']
                delta = np.linalg.norm(arrays[route+'_low'][:, :2]-arrays[route+'_high'][:, :2], axis=1)
                pairs.append(dict(dataset=scene, seed=seed, route=route,
                                  short_wait_first_departure_s=low['first_departure_sample_s'],
                                  long_wait_first_departure_s=high['first_departure_sample_s'],
                                  mean_xy_difference_m=float(delta.mean()), max_xy_difference_m=float(delta.max())))
    assert len(rows) == 96 and len(pairs) == 12
    for filename, items in (('hold_metrics.csv', rows), ('wait_pair_metrics.csv', pairs)):
        with (root / filename).open('w') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(items[0]))
            writer.writeheader()
            writer.writerows(items)
    summary = {}
    for scene in manifest['cases']:
        summary[scene] = {}
        for route in ('user', 'coc'):
            summary[scene][route] = {}
            for level in ('low', 'high'):
                subset = [x for x in rows if x['dataset'] == scene and x['condition'] == route+'_'+level and x['assessed_wait'] == level]
                summary[scene][route][level] = dict(
                    outputs=len(subset), violations=sum(x['exceeds_with_0_01_m_tolerance'] for x in subset),
                    wait_seconds=subset[0]['hold_seconds'],
                    maximum_displacement_during_hold_m=max(x['maximum_displacement_during_hold_m'] for x in subset),
                    first_departures_s=[x['first_departure_sample_s'] for x in subset])
    r.write_json(root/'validation.json', dict(status='PASS', trajectories_replayed=48,
                 scalar_displacement_replay=True, maximum_float32_replay_error_m=replay_error,
                 exact_self_splices=6, assessments_replayed=len(rows), user_added_token_counts=token_counts,
                 all_user_short_long_pairs_equal_token_count=True))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5), constrained_layout=True)
    times = np.arange(1, 65)*.1
    colors = {'native':'#777777', 'low':'#c43b36', 'high':'#2072b8', 'neutral':'#439647'}
    for col, scene in enumerate(manifest['cases']):
        for row, route in enumerate(('user', 'coc')):
            ax = axes[row, col]
            for level in ('native', 'low', 'high', 'neutral'):
                condition = level if level == 'native' else route+'_'+level
                values = np.array([d['conditions'][condition]['assessments']['low']['radial_displacement_m'] for d in saved[scene]])
                label = {'low':'0.5s hold', 'high':'2.0s hold'}.get(level, level)
                ax.plot(times, values.mean(axis=0), color=colors[level], label=label)
                ax.fill_between(times, values.min(axis=0), values.max(axis=0), color=colors[level], alpha=.1)
            ax.axhline(.2, linestyle='--', color='#333333', label='0.2m hold radius')
            ax.axvline(.5, linestyle=':', color=colors['low'])
            ax.axvline(2., linestyle=':', color=colors['high'])
            ax.set(title=scene+': '+('user instruction' if route == 'user' else 'forced CoC addition'),
                   xlabel='Prediction time (s)', ylabel='Radial displacement from current position (m)', xlim=(0, 2.2), ylim=(0, None))
            # Show only the relevant hold windows; the raw 6.4s outputs remain archived.
            ymax = max(max(d['conditions'][route+'_'+level]['assessments']['high']['radial_displacement_m'][:22])
                       for d in saved[scene] for level in ('low', 'high', 'neutral'))
            ax.set_ylim(0, max(.3, ymax*1.07))
            ax.grid(alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=5, frameon=False)
    fig.suptitle('Alpamayo R1: supplied position-hold durations\nTwo existing low-speed inputs; three paired action seeds')
    for ext in ('pdf', 'png'):
        fig.savefig(root / f'position_hold_compliance.{ext}', dpi=170)
    lines = ['# Alpamayo R1 정지 유지 시간 검사', '',
             '- 기존 여섯 입력 중 현재 구간 평균 속도가 0.5m/s 이하인 PhysicalAI·nuScenes 입력 각 1개를 사용했다.',
             '- 0.5초와 2초 동안 현재 위치를 유지하도록 요청했다. 정지 유지는 현재 위치 중심 반경 0.2m로 정의하며, 판정에는 0.01m 여유를 적용한다.',
             '- 대기 구간은 0.1초마다의 예측 waypoint로 검사하고 대기 종료 시점도 포함한다. 이후 이동은 허용되지만 요구하지 않는다.',
             '- 각 입력에 세 action seed와 여덟 조건을 적용했다. 총 48개 궤적이고 조건별 분모는 두 입력×세 seed이다.',
             '- 조건: native, exact self-splice, 사용자 프롬프트의 짧은/긴/무관 규칙, 강제 CoC의 짧은/긴/무관 규칙.', '',
             '| 입력 | 규칙 입력 경로 | 대기 시간 | 대기 중 반경 초과 | 대기 중 최대 변위(m) | 최초 반경 이탈 시점(s), 세 seed |',
             '|---|---|---:|---:|---:|---|']
    for scene, routes in summary.items():
        for route, levels in routes.items():
            for level, values in levels.items():
                lines.append(f"| {scene} | {route} | {values['wait_seconds']:.1f} | {values['violations']}/{values['outputs']} | {values['maximum_displacement_during_hold_m']:.3f} | {values['first_departures_s']} |")
    lines += ['', '## 규칙 원문', '', '> '+r.rule(.5), '', '> '+r.rule(2.), '', '## 사용자 규칙에 대한 CoC 응답 원문', '']
    for scene, records in saved.items():
        for d in records:
            lines.append(f"### {scene}, seed {d['action_seed']}")
            for condition in ('native', 'user_low', 'user_high', 'user_neutral'):
                lines.append(f"- {condition}: {d['conditions'][condition]['coc']}")
    lines += ['', '## 해석 범위', '',
              '- 이 검사는 실제 STOP 지시·정지선·해제 근거를 판정하지 않는다. 대기 규칙은 공급한 실험 정책이다.',
              '- 두 장면 모두 완전한 정지 상태라고 가정하지 않는다. 현재 속도는 manifest에 기록하며 작은 위치 반경을 허용한다.',
              '- 반경 안의 미세 이동은 허용된다. 연속 시간 정지나 샘플 사이 움직임을 보증하지 않는다.',
              '- 강제 CoC는 모델이 자발적으로 생성한 규칙이 아니다. 프롬프트와 강제 continuation 개입을 분리해 보고한다.',
              '- 무관 문장은 CoC token 길이에 맞춘 반복 context 문장이다. 사용자 입력 token 수는 validation.json에 별도로 기록한다.',
              '- nuScenes 입력은 제삼자 PhysicalAI 형식 변환 자료이고 전방 망원 영상은 crop이다. 동일 센서 분포의 공식 벤치마크 비교가 아니다.',
              '- 새 학습·사람 라벨링·영상 다운로드 없이 보존된 입력을 그대로 재사용했다. 일반적인 도로 실패율이나 EBLC의 개선 효과를 입증하는 실험은 아니다.']
    (root / 'REPORT_KO.md').write_text('\n'.join(lines)+'\n')
    r.write_json(root/'RESULT.json', dict(status='COMPLETE', project_id='guardsynth-coc',
                 trajectories=48, cases=2, paired_seeds=3, summary=summary, validation='PASS'))
    r.write_json(root/'report_checksums.json', {str(p.relative_to(root)):r.digest(p) for p in root.rglob('*') if p.is_file()})
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
