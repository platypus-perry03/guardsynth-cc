"""Fault-injection evaluation of the two specifications used for CoC learning.

Reuses the maintained validators, lowering, renderers, and platform SMT engine.
Evidence comparisons, fixed-grammar parsing, and probes are evaluation additions;
they must not be described as checks deployed in the historical training runs.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import temporal_preservation as temporal

ROOT = temporal.ROOT
sys.path.insert(0, str(ROOT / 'projects/04-guardsynth-coc/experiments/paper1_external_methods'))
import position_hold_training_profile as hold
from guard_synth_eblc.core_ir import parse_core_model
from guard_synth_eblc.smt_compiler import compile_core_model, solve_assignment

PROTOCOL = Path(__file__).with_name('learning_specification_faults_protocol_v0_1.json')
TEMPORAL_INPUT = temporal.BASE / 'temporal-protocol-2026-09-29-001/paired_dataset.jsonl'
TEMPORAL_BRIDGE = TEMPORAL_INPUT.with_name('bridge.json')
HOLD_INPUT = ROOT / ('projects/04-guardsynth-coc/artifacts/public/'
                     'paper1-position-hold-training-001/position-hold-training-2026-10-08-001/test.jsonl')
OUTPUT = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-learning-specification-faults-001'
PROFILES = {'pedestrian_entry': temporal, 'position_hold': hold}
LAYERS = ('structural', 'consistency', 'logic_rule', 'evidence', 'sentence')
KERNEL = LAYERS[:3]


def read_rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def duration_field(profile):
    return 'release_clear_ms' if profile == 'pedestrian_entry' else 'hold_ms'


def other_duration(profile, value):
    options = (500, 1500) if profile == 'pedestrian_entry' else (500, 2000)
    return options[1] if value == options[0] else options[0]


def parse_sentence(profile, text):
    """Recognize exact supported templates; source metadata is not inferred."""
    if profile == 'pedestrian_entry':
        pattern = (r'Do not enter the pedestrian conflict zone while it is occupied\. '
                   r'Enter only after the zone has remained clear for at least (0\.5|1\.5) s\.')
        match = re.fullmatch(pattern, text)
        if match is None:
            raise ValueError('unsupported pedestrian CNL')
        return temporal.contract(float(match[1]))
    pattern = (r"Hold the ego vehicle's initial position for at least (?P<t>0\.5|2\.0) s\. "
               r'At every listed waypoint with t <= (?P=t) s, including the endpoint, '
               r'the radial XY distance from the initial position must be at most 0\.200 m\. '
               r'Movement after that period is permitted\.')
    match = re.fullmatch(pattern, text)
    if match is None:
        raise ValueError('unsupported position-hold CNL')
    return hold.contract(round(float(match['t']) * 1000))


def base_cases():
    cases = []
    bridge = {p['contract']['release_clear_ms']: p['contract']
              for p in json.loads(TEMPORAL_BRIDGE.read_text())}
    rows = [r for r in read_rows(TEMPORAL_INPUT)
            if r['seed'] == 42 and r['split'] == 'benchmark_regression']
    scenes = sorted({r['scene_id'] for r in rows})[:12]
    for row in rows:
        if row['scene_id'] not in scenes:
            continue
        scene = temporal.world.make_scene(row['scene_id'], row['generator_seed'], 'test')
        duration = 500 if row['contract_level'] == 'short' else 1500
        spec = deepcopy(bridge[duration])
        assert spec == temporal.contract(duration / 1000)
        example = next(e for e in temporal.world.generate_temporal_examples(
            row['scene_id'] - 20000 + 1, row['generator_seed'], 'test')
            if e.scene.scene_id == row['scene_id'] and e.required_clear_duration == duration / 1000)
        expected_prompt = temporal.world.prompt_for(
            temporal.replace(example, rich_coc_text=temporal.world.COC_TEXT + ' ' + temporal.render(spec)),
            'RICH_COC')
        assert row['prompts']['P2'] == expected_prompt
        assert hashlib.sha256(temporal.world.render_storyboard(scene).tobytes()).hexdigest() == row['image_pixel_sha256']
        cases.append(dict(profile='pedestrian_entry',
                          id=f"temporal-{row['scene_id']}-{duration}", specification=spec,
                          clear_ms=round(scene.clear_time * 1000),
                          candidates=[dict(label=c.label,
                                           entry_ms=None if c.entry_time is None else round(c.entry_time * 1000))
                                      for c in scene.candidates],
                          archive_row=dict(seed=row['seed'], split=row['split'], scene_id=row['scene_id'],
                                           contract_level=row['contract_level'])))
    rows = [r for r in read_rows(HOLD_INPUT)
            if r['encoding'] == 'interval_maxima' and r['id'].split('-')[2] == '0']
    profiles = sorted({r['profile_id'] for r in rows})[:12]
    for row in rows:
        if row['profile_id'] not in profiles:
            continue
        spec = row['eblc']
        assert spec == hold.contract(row['hold_ms'])
        assert row['prompts']['p2'].splitlines()[1] == 'Constraint: ' + hold.render(spec)
        cases.append(dict(profile='position_hold', id=row['id'], specification=spec,
                          candidates=row['candidates'], archive_row=dict(id=row['id'], profile_id=row['profile_id'])))
    assert Counter(c['profile'] for c in cases) == dict.fromkeys(PROFILES, 24)
    return cases


def mutate_core(profile, core, specification, kind):
    if kind == 'reverse_comparison':
        if profile == 'pedestrian_entry':
            core['clauses'][0]['formula']['right']['op'] = 'le'
        else:
            core['clauses'][-1]['formula']['op'] = 'ge'
    if kind == 'delete_release':
        if profile == 'pedestrian_entry':
            core['clauses'][0]['formula'] = temporal.lit(True)
        else:
            # Forgetting release applies the same radius after the hold expires.
            template = deepcopy(core['clauses'][-1])
            for i, time_ms in enumerate(hold.TIMES_MS):
                if time_ms <= specification['hold_ms']:
                    continue
                clause = deepcopy(template)
                clause['id'] = f'erroneous_post_hold_{i}'
                x, y = hold.variable(f'x_{i}'), hold.variable(f'y_{i}')
                clause['formula'] = hold.binary('le', hold.binary('add', hold.binary('mul', x, x),
                    hold.binary('mul', y, y)), hold.literal(specification['radius_mm'] ** 2))
                core['clauses'].append(clause)
    return core


def probes(case, source):
    """Independent integer rule calculations, not parsed CNL or compiled logic."""
    if case['profile'] == 'pedestrian_entry':
        clear = case['clear_ms']
        samples = [(f"archived-{c['label']}", c['entry_ms'], c['entry_ms'] is not None)
                   for c in case['candidates']]
        samples += [(f'boundary-{delta}-{enters}', clear + source['release_clear_ms'] + delta, enters)
                    for delta in (-1, 0, 1) for enters in (False, True)]
        for name, entry, enters in samples:
            expected = 'SAT' if not enters or entry - clear >= source['release_clear_ms'] else 'UNSAT'
            yield name, {('entry_ms', None): entry or 0, ('clear_ms', None): clear,
                         ('enters', None): enters}, expected
        return
    samples = [(f"archived-{c['label']}", c['xy_mm']) for c in case['candidates']]
    for i in range(1, len(hold.TIMES_MS)):
        for point in ([199, 0], [200, 0], [201, 0], [120, 160], [150, 150]):
            points = [[0, 0] for _ in hold.TIMES_MS]
            points[i] = point
            samples.append((f'sample-{i}-{point[0]}-{point[1]}', points))
    for name, points in samples:
        maximum = max(x*x + y*y for time_ms, (x, y) in zip(hold.TIMES_MS, points)
                      if time_ms <= source['hold_ms'])
        expected = 'SAT' if maximum <= source['radius_mm'] ** 2 else 'UNSAT'
        values = {(f'{axis}_{i}', None): value for i, xy in enumerate(points)
                  for axis, value in zip(('x', 'y'), xy)}
        yield name, values, expected


def evaluate(case, kind):
    profile = case['profile']
    module = PROFILES[profile]
    original = deepcopy(case['specification'])
    source, specification = deepcopy(original), deepcopy(original)
    field = duration_field(profile)
    if kind in ('duration_change', 'shared_source_error'):
        specification[field] = other_duration(profile, specification[field])
    if kind == 'shared_source_error':
        source = deepcopy(specification)
    if kind == 'unit_error':
        specification['time_unit'] = 's'
    flags = dict.fromkeys(LAYERS, None)
    unknown = False
    structural_error = None
    text, core, consistency = None, None, None
    checked = []
    try:
        module.validate(specification)
        flags['structural'] = False
    except ValueError as error:
        flags['structural'] = True
        structural_error = str(error)
    if not flags['structural']:
        flags['evidence'] = specification != source
        core = mutate_core(profile, module.lower(specification), specification, kind)
        compiled = compile_core_model(parse_core_model(core))
        consistency = solve_assignment(compiled, {})['status']
        flags['consistency'] = consistency == 'UNSAT'
        unknown |= consistency == 'UNKNOWN'
        for name, values, expected in probes(case, source):
            result = solve_assignment(compiled, values)
            unknown |= result['status'] == 'UNKNOWN'
            checked.append(dict(id=name, assignments=[dict(name=k[0], value=v) for k, v in values.items()],
                                expected=expected, observed=result['status'], reason_unknown=result['reason_unknown']))
        flags['logic_rule'] = any(c['observed'] != c['expected'] and c['observed'] != 'UNKNOWN' for c in checked)
        text = module.render(specification)
        if kind == 'cnl_duration':
            text = text.replace(f'{specification[field] / 1000:.1f} s',
                                f'{other_duration(profile, specification[field]) / 1000:.1f} s')
        if kind == 'cnl_negation':
            text = text.replace('Do not enter', 'Enter') if profile == 'pedestrian_entry' else text.replace('must be at most', 'must not be at most')
        try:
            flags['sentence'] = parse_sentence(profile, text) != specification
        except ValueError:
            flags['sentence'] = True
    return dict(base_id=case['id'], profile=profile, kind=kind,
                original_specification=original, trusted_source=source, candidate_specification=specification,
                logical_model=core, cnl=text, structural_error=structural_error,
                consistency=consistency, probes=checked, layers=flags, unknown=unknown,
                kernel_detected=any(flags[layer] for layer in KERNEL),
                detected=any(flags.values()), accepted=not any(flags.values()) and not unknown,
                erroneous=kind != 'valid', supported_error=kind not in ('valid', 'shared_source_error'))


def summarize(records):
    valid = [r for r in records if r['kind'] == 'valid']
    errors = [r for r in records if r['supported_error']]
    shared = [r for r in records if r['kind'] == 'shared_source_error']
    return dict(cases=len(records), valid_cases=len(valid), valid_accepted=sum(r['accepted'] for r in valid),
                supported_errors=len(errors), supported_detected=sum(r['detected'] for r in errors),
                supported_kernel_detected=sum(r['kernel_detected'] for r in errors),
                shared_source_errors=len(shared), shared_source_missed=sum(r['accepted'] for r in shared),
                unknown_cases=sum(r['unknown'] for r in records),
                probe_queries=sum(len(r['probes']) for r in records),
                by_kind={kind: dict(cases=len(rows), detected=sum(r['detected'] for r in rows),
                                   kernel_detected=sum(r['kernel_detected'] for r in rows),
                                   layer_flags={layer: sum(r['layers'][layer] is True for r in rows) for layer in LAYERS})
                         for kind in dict.fromkeys(r['kind'] for r in records)
                         for rows in [[r for r in records if r['kind'] == kind]]})


def run(run_id):
    protocol = json.loads(PROTOCOL.read_text())
    cases = base_cases()
    target = OUTPUT / run_id
    target.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), PROTOCOL, Path(temporal.__file__), Path(hold.__file__),
               Path(temporal.world.__file__), TEMPORAL_INPUT, TEMPORAL_BRIDGE, HOLD_INPUT,
               ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/core_ir.py',
               ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/smt_compiler.py']
    manifest = dict(project_id='guardsynth-coc', task_id=protocol['task_id'], run_id=run_id,
                    status='PROTOCOL_AND_INPUTS_FROZEN', created_at=datetime.now(timezone.utc).isoformat(),
                    inputs=[str(p.relative_to(ROOT)) for p in sources],
                    input_hashes={str(p.relative_to(ROOT)): digest(p) for p in sources},
                    runtime=dict(python=sys.version, executable=sys.executable),
                    protocol=protocol)
    dump(target / 'RUN_MANIFEST.json', manifest)
    dump(target / 'protocol.json', protocol)
    (target / 'base_cases.jsonl').write_text(''.join(json.dumps(c) + '\n' for c in cases))
    records = []
    with (target / 'mutations.jsonl').open('w') as stream:
        for case in cases:
            for kind in protocol['variants']:
                row = evaluate(case, kind)
                records.append(row)
                stream.write(json.dumps(row) + '\n')
    result = dict(project_id='guardsynth-coc', task_id=protocol['task_id'], status='COMPLETE',
                  aggregate=summarize(records),
                  profiles={p: summarize([r for r in records if r['profile'] == p]) for p in PROFILES},
                  interpretation=protocol['claim_scope'])
    dump(target / 'RESULT.json', result)
    report = ['# 학습용 명세 오류 주입 평가', '',
              '학습에 사용한 보행자 진입 및 위치 유지 명세의 기존 검증기·논리 변환·렌더러를 그대로 호출했다. '
              '근거 비교, 두 고정 문법 파서, 프로브 및 집계는 이번 평가에서 추가했다. 과거 학습에 적용한 검사라고 해석하지 않는다.', '',
              '| 명세 | 유효 사례 통과 | 지원 오류 검출 | 문장·근거 검사 제외 시 검출 | 근거·명세 동시 오류 미검출 |',
              '|---|---:|---:|---:|---:|']
    for profile, stats in result['profiles'].items():
        report.append(f"| {profile} | {stats['valid_accepted']}/{stats['valid_cases']} | "
                      f"{stats['supported_detected']}/{stats['supported_errors']} | "
                      f"{stats['supported_kernel_detected']}/{stats['supported_errors']} | "
                      f"{stats['shared_source_missed']}/{stats['shared_source_errors']} |")
    report += ['', '## 평가 단위와 오류 대응', '',
               '각 명세는 두 기간 규칙 × 12개 보관 사례로 24개 맥락을 구성하고, 맥락마다 유효 대조와 7개 오류 변형을 평가했다. '
               '24개는 서로 다른 계약 값 24개나 독립 도로 장면 24개가 아니다.', '',
               '기간 변경은 지원되는 두 값 사이에서 바꾸어 구조 검사가 자명하게 거부하지 않도록 했다. '
               '비교 역전은 보행자의 진입 부등식 또는 위치 유지 끝점의 거리 부등식을 뒤집었다. '
               '해제 조건 누락은 보행자의 진입 제한 제거, 위치 유지의 경우 종료 뒤에도 모든 표본에 거리 제한을 적용하는 오류로 대응시켰다.', '',
               '## 한계', '',
               '기존 두 명세와 실제 보관 후보를 검사하지만 문장 파서는 이번에 추가한 평가 장치다. '
               '모델 재학습이나 예측 준수율 개선을 측정하지 않았다. 고정 문법과 주입한 오류 유형의 검사이며, '
               '임의 자연어 의미 검증이나 현실 안전 보장이 아니다. 앞선 별도 시간 명세의 192건과 합산하지 않는다.', '',
               f"UNKNOWN 사례: {result['aggregate']['unknown_cases']}; 구체 후보 질의: {result['aggregate']['probe_queries']}.", '',
               '재현 명령: `runtime/alpamayo/ar1_venv/bin/python '
               'projects/04-guardsynth-coc/experiments/paper1_cnl_learning/learning_specification_faults.py '
               '--run-id <미사용-run-id>`', '']
    (target / 'REPORT_KO.md').write_text('\n'.join(report))
    manifest['status'] = 'COMPLETE'
    manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
    manifest['output_hashes'] = {p.name: digest(p) for p in target.iterdir() if p.name != 'RUN_MANIFEST.json'}
    dump(target / 'RUN_MANIFEST.json', manifest)
    print(json.dumps(dict(output=str(target), aggregate=result['aggregate'], profiles=result['profiles']), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    run(parser.parse_args().run_id)
