"""Project guardsynth-coc: bounded composition diagnostic, not a new solver.

Reuses the two learning-profile lowerers and the unmodified platform compiler.
All new source conditions and their contexts are supplied synthetic inputs.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import sys

import temporal_preservation as entry

ROOT = entry.ROOT
sys.path.insert(0, str(ROOT / 'projects/04-guardsynth-coc/experiments/paper1_external_methods'))
import position_hold_training_profile as hold
from guard_synth_eblc.core_ir import parse_core_model
from guard_synth_eblc.smt_compiler import compile_core_model, check_queries
from cli.solver_runtime import configure_project_z3

PROTOCOL = Path(__file__).with_name('constraint_composition_protocol_v0_1.json')
SOURCES = json.loads(PROTOCOL.read_text())['source_documents']
OUTPUT = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-constraint-composition-001'
lit, var, binary = entry.lit, entry.var, entry.binary


def conjunction(items):
    return dict(op='and', args=items) if len(items) > 1 else items[0] if items else lit(True)


def clause(name, formula, source):
    return dict(id=name, kind='INVARIANT', enforcement='INITIAL', formula=formula,
                source_refs=[source], description=name)


def build_case(family, p):
    """Build source groups and shared context separately; never repair inputs."""
    components = []
    def add(name, formulas, natural, formal, specification=None):
        document = SOURCES[f'{family}.{name}']
        source = document['document_id']
        components.append(dict(id=name, source_kind=document['kind'], source_document=document,
                               natural_language=natural, formal_specification=formal,
                               source_refs=[source], specification=specification,
                               clauses=[clause(f'{name}_{i}', f, source) for i, f in enumerate(formulas)]))
    context = []
    def assume(name, formula):
        context.append(clause(name, formula, f'synthetic:{family}/context/{name}'))
    if family == 'entry_deadline':
        spec = entry.contract(p['wait_ms'] / 1000)
        model = entry.lower(spec)
        add('entry_release', [c['formula'] for c in model['clauses']],
            f"Enter only after {p['wait_ms']} ms have elapsed since clearance.",
            rf"e\Rightarrow u\ge\tau+{p['wait_ms']}", spec)
        add('entry_deadline', [binary('implies', var('enters'),
                                    binary('le', var('entry_ms'), lit(p['deadline_ms'])))],
            f"If entry occurs, its time must not exceed {p['deadline_ms']} ms.",
            rf"e\Rightarrow u\le {p['deadline_ms']}")
        assume('clearance_observation', binary('eq', var('clear_ms'), lit(p['clear_ms'])))
        assume('entry_obligation', binary('eq', var('enters'), lit(p['required_entry'])))
        assume('nonnegative_time', binary('ge', var('entry_ms'), lit(0)))
    elif family == 'hold_departure':
        spec = hold.contract(p['hold_ms'])
        model = hold.lower(spec)
        add('position_hold', [c['formula'] for c in model['clauses']],
            f"Stay within 200 mm of the origin through {p['hold_ms']} ms, including the endpoint.",
            rf"\bigwedge_{{t_i\le {p['hold_ms']}}}(x_i^2+y_i^2\le 200^2)", spec)
        index = hold.TIMES_MS.index(p['departure_sample_ms'])
        add('departure_requirement', [binary('ge', var(f'x_{index}'), lit(p['required_x_mm']))],
            f"At the {p['departure_sample_ms']} ms sample, reach x of at least {p['required_x_mm']} mm.",
            rf"x_{{{p['departure_sample_ms']}}}\ge {p['required_x_mm']}")
        for i in range(len(hold.TIMES_MS)):
            assume(f'straight_path_{i}', binary('eq', var(f'y_{i}'), lit(0)))
            assume(f'nonnegative_x_{i}', binary('ge', var(f'x_{i}'), lit(0)))
        assume('initial_origin', binary('eq', var('x_0'), lit(0)))
    else:
        names = ['speed_mm_s', 'distance_mm'] if family == 'speed_progress' else ['stop_ms', 'release_ms', 'entry_ms']
        model = dict(grammar_version='eblc-core-v0.1', model_id=family, horizon=2,
                     declarations=[dict(name=n, sort='INT', time_varying=False, unit='1',
                                        enum_name=None, enum_values=[], frame=None,
                                        source_refs=[f'synthetic:{family}/context']) for n in names])
        for name in names:
            assume(f'nonnegative_{name}', binary('ge', var(name), lit(0)))
        if family == 'speed_progress':
            assume('constant_speed_model', binary('eq', var('distance_mm'),
                    binary('mul', var('speed_mm_s'), lit(p['horizon_s']))))
            add('speed_cap', [binary('le', var('speed_mm_s'), lit(p['cap_mm_s']))],
                f"Speed must not exceed {p['cap_mm_s']} mm/s.", rf"v\le {p['cap_mm_s']}")
            add('minimum_progress', [binary('ge', var('distance_mm'), lit(p['minimum_mm']))],
                f"Travel at least {p['minimum_mm']} mm within {p['horizon_s']} s.", rf"x\ge {p['minimum_mm']}")
        else:
            assume('stop_anchor', binary('eq', var('stop_ms'), lit(0)))
            add('release_wait', [binary('ge', var('release_ms'), binary('add', var('stop_ms'), lit(p['wait_ms'])))],
                f"Release no earlier than {p['wait_ms']} ms after stopping.", rf"r\ge s+{p['wait_ms']}")
            add('transition_delay', [binary('ge', var('entry_ms'), binary('add', var('release_ms'), lit(p['delay_ms'])))],
                f"Assume entry takes at least {p['delay_ms']} ms after release.", rf"u\ge r+{p['delay_ms']}")
            add('entry_deadline', [binary('le', var('entry_ms'), binary('add', var('stop_ms'), lit(p['deadline_ms'])))],
                f"Enter no later than {p['deadline_ms']} ms after stopping.", rf"u\le s+{p['deadline_ms']}")
    refs = {ref for item in model['declarations'] + context for ref in item['source_refs']}
    refs.update(ref for c in components for ref in c['source_refs'])
    model.update(clauses=context, queries=[], source_refs=sorted(refs),
                 claim_scope='BOUNDED_SYNTHETIC_COMPOSITION_NOT_VEHICLE_SAFETY')
    return dict(family=family, parameters=p, context_model=model, constraints=components)


def generate_cases(protocol):
    rows = []
    def add(family, **params):
        case = build_case(family, params)
        case['id'] = f'{family}-{sum(r["family"] == family for r in rows):03d}'
        rows.append(case)
    for clear, wait, offset in product(protocol['clearance_ms'], protocol['wait_ms'], protocol['boundary_offsets']):
        add('entry_deadline', clear_ms=clear, wait_ms=wait, deadline_ms=clear + wait + offset, required_entry=True)
        if offset < 0:
            add('entry_deadline', clear_ms=clear, wait_ms=wait, deadline_ms=clear + wait + offset, required_entry=False)
    for duration in protocol['hold_ms']:
        after = next(t for t in hold.TIMES_MS if t > duration)
        for time, distance in product((duration, after), protocol['required_x_mm']):
            add('hold_departure', hold_ms=duration, departure_sample_ms=time, required_x_mm=distance)
    for cap, horizon, offset in product(protocol['speed_caps_mm_s'], protocol['travel_horizons_s'], protocol['boundary_offsets']):
        add('speed_progress', cap_mm_s=cap, horizon_s=horizon, minimum_mm=cap * horizon + offset)
    for wait, delay, offset in product(protocol['wait_ms'], protocol['transition_delays_ms'], protocol['boundary_offsets']):
        add('three_way_timing', wait_ms=wait, delay_ms=delay, deadline_ms=wait + delay + offset)
    assert len(rows) == protocol['planned_case_count']
    return rows


def expected(case, subset):
    """Analytic integer feasibility reference, independent of the Core formulas."""
    if len(subset) < len(case['constraints']):
        return 'SAT'  # Every proper subset in the specified grid is feasible.
    p, family = case['parameters'], case['family']
    if family == 'entry_deadline':
        feasible = not p['required_entry'] or p['clear_ms'] + p['wait_ms'] <= p['deadline_ms']
    elif family == 'hold_departure':
        feasible = p['departure_sample_ms'] > p['hold_ms'] or p['required_x_mm'] <= 200
    elif family == 'speed_progress':
        feasible = p['minimum_mm'] <= p['cap_mm_s'] * p['horizon_s']
    else:
        feasible = p['wait_ms'] + p['delay_ms'] <= p['deadline_ms']
    return 'SAT' if feasible else 'UNSAT'


def valid_witness(case, subset, w):
    """Check source conditions numerically, without evaluating Core expressions."""
    p, family = case['parameters'], case['family']
    ids = {case['constraints'][i]['id'] for i in subset}
    if family == 'entry_deadline':
        return (w['clear_ms'] == p['clear_ms'] and w['enters'] == p['required_entry'] and w['entry_ms'] >= 0
                and ('entry_release' not in ids or not w['enters'] or w['entry_ms'] >= p['clear_ms'] + p['wait_ms'])
                and ('entry_deadline' not in ids or not w['enters'] or w['entry_ms'] <= p['deadline_ms']))
    if family == 'hold_departure':
        return (w['x_0'] == 0 and all(w[f'y_{i}'] == 0 and w[f'x_{i}'] >= 0 for i in range(len(hold.TIMES_MS)))
                and ('position_hold' not in ids or all(w[f'x_{i}'] ** 2 + w[f'y_{i}'] ** 2 <= 200 ** 2
                     for i, t in enumerate(hold.TIMES_MS) if t <= p['hold_ms']))
                and ('departure_requirement' not in ids or w[f'x_{hold.TIMES_MS.index(p["departure_sample_ms"])}'] >= p['required_x_mm']))
    if family == 'speed_progress':
        return (w['speed_mm_s'] >= 0 and w['distance_mm'] == w['speed_mm_s'] * p['horizon_s']
                and ('speed_cap' not in ids or w['speed_mm_s'] <= p['cap_mm_s'])
                and ('minimum_progress' not in ids or w['distance_mm'] >= p['minimum_mm']))
    return (w['stop_ms'] == 0 and w['release_ms'] >= 0 and w['entry_ms'] >= 0
            and ('release_wait' not in ids or w['release_ms'] >= p['wait_ms'])
            and ('transition_delay' not in ids or w['entry_ms'] >= w['release_ms'] + p['delay_ms'])
            and ('entry_deadline' not in ids or w['entry_ms'] <= p['deadline_ms']))


def evaluate(case):
    raw = deepcopy(case['context_model'])
    subsets = [s for size in range(len(case['constraints']) + 1)
               for s in combinations(range(len(case['constraints'])), size)]
    for k, subset in enumerate(subsets):
        raw['queries'].append(dict(id=f'subset_{k}', expected=expected(case, subset), classification='CONSISTENCY',
             formula=conjunction([c['formula'] for i in subset for c in case['constraints'][i]['clauses']]),
             source_refs=[ref for i in subset for ref in case['constraints'][i]['source_refs']] or raw['source_refs'],
             description='Shared context plus selected source constraints.'))
    compiled = compile_core_model(parse_core_model(raw))
    checked = check_queries(compiled)
    queries = []
    for subset, result in zip(subsets, checked['results']):
        witness = None if result['witness'] is None else {
            x['declaration']: result['witness'][x['smt_symbol']] for x in compiled.symbol_table['symbols']}
        result.update(case_id=case['id'], selected=list(subset), witness=witness,
                      witness_valid=None if witness is None else valid_witness(case, subset, witness))
        queries.append(result)
    cores = [q['selected'] for q in queries if q['status'] == 'UNSAT' and all(
        r['status'] == 'SAT' for r in queries if set(r['selected']) < set(q['selected']))]
    return dict(case_id=case['id'], family=case['family'], full_status=queries[-1]['status'],
                expected_full=queries[-1]['expected'], context_sat=queries[0]['status'] == 'SAT',
                components_sat=all(q['status'] == 'SAT' for q in queries if len(q['selected']) == 1),
                pairs_sat=all(q['status'] == 'SAT' for q in queries if len(q['selected']) == 2),
                minimal_conflict_groups=[[case['constraints'][i]['id'] for i in core] for core in cores],
                queries=queries, core_model=raw)


def summarize(rows):
    queries = [q for row in rows for q in row['queries']]
    conflicts = [r for r in rows if r['full_status'] == 'UNSAT']
    return dict(cases=len(rows), full_sat=sum(r['full_status'] == 'SAT' for r in rows),
                full_unsat=len(conflicts), queries=len(queries),
                unknown=sum(q['status'] == 'UNKNOWN' for q in queries),
                mismatches=sum(not q['matches_expected'] for q in queries),
                sat_witnesses=sum(q['witness'] is not None for q in queries),
                invalid_witnesses=sum(q['witness_valid'] is False for q in queries),
                all_components_sat=sum(r['components_sat'] and r['context_sat'] for r in rows),
                component_only_detected=sum(not r['components_sat'] for r in conflicts),
                pairwise_detected=sum(not r['pairs_sat'] for r in conflicts),
                minimal_conflict_groups=sum(bool(r['minimal_conflict_groups']) for r in conflicts),
                pairwise_sat_full_unsat=sum(r['pairs_sat'] for r in conflicts))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(run_id):
    protocol = json.loads(PROTOCOL.read_text())
    cases = generate_cases(protocol)
    target = OUTPUT / run_id
    target.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__), PROTOCOL, Path(entry.__file__), Path(hold.__file__),
              ROOT / 'projects/04-guardsynth-coc/tests/unit/test_constraint_composition.py',
              ROOT / 'cli/solver_runtime.py',
              ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/core_ir.py',
              ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/smt_compiler.py']
    manifest = dict(project_id='guardsynth-coc', task_id=protocol['task_id'], run_id=run_id,
                    status='INPUTS_FROZEN', created_at=datetime.now(timezone.utc).isoformat(),
                    inputs=[str(p.relative_to(ROOT)) for p in inputs],
                    input_hashes={str(p.relative_to(ROOT)): digest(p) for p in inputs},
                    runtime=dict(python=sys.version, solver=configure_project_z3(ROOT).manifest()))
    dump(target / 'RUN_MANIFEST.json', manifest)
    dump(target / 'protocol.json', protocol)
    (target / 'cases.jsonl').write_text(''.join(json.dumps(c) + '\n' for c in cases))
    rows = [evaluate(c) for c in cases]
    (target / 'queries.jsonl').write_text(''.join(json.dumps(q) + '\n' for row in rows for q in row['queries']))
    (target / 'compositions.jsonl').write_text(''.join(json.dumps({k: v for k, v in row.items() if k != 'queries'}) + '\n' for row in rows))
    stats = summarize(rows)
    assert stats['queries'] == protocol['planned_subset_queries']
    assert stats['unknown'] == stats['mismatches'] == stats['invalid_witnesses'] == 0, stats
    assert stats['all_components_sat'] == len(cases), stats
    assert stats['minimal_conflict_groups'] == stats['full_unsat'], stats
    # Every inconsistent grid point has a separately solved equality-boundary repair.
    repairs = 0
    for case, row in zip(cases, rows):
        if row['full_status'] != 'UNSAT':
            continue
        p = dict(case['parameters'])
        field = {'entry_deadline': 'deadline_ms', 'hold_departure': 'required_x_mm',
                 'speed_progress': 'minimum_mm', 'three_way_timing': 'deadline_ms'}[case['family']]
        p[field] += 1 if field == 'deadline_ms' else -1
        match = next(r for c, r in zip(cases, rows) if c['family'] == case['family'] and c['parameters'] == p)
        assert match['full_status'] == 'SAT'
        repairs += 1
    stats['boundary_repairs_sat'] = repairs
    result = dict(project_id='guardsynth-coc', task_id=protocol['task_id'], status='COMPLETE', aggregate=stats,
                  families={f: summarize([r for r in rows if r['family'] == f]) for f in protocol['families']},
                  claim_scope=protocol['claim_scope'])
    dump(target / 'RESULT.json', result)
    report = ['# 조합 제약의 모순 검사', '', '소유 프로젝트: `guardsynth-coc`', '',
              '기존 보행자 진입·위치 유지 변환기와 플랫폼 SMT 컴파일러를 재사용한 합성 명세 평가다. '
              '실제 사고 재현이나 주행 모델 재학습 실험이 아니다.', '',
              '| 조합 | 사례 | 전체 SAT | 전체 UNSAT | 단독 검사로 발견 | 쌍별 검사로 발견 |',
              '|---|---:|---:|---:|---:|---:|']
    for family, s in result['families'].items():
        report.append(f"| {family} | {s['cases']} | {s['full_sat']} | {s['full_unsat']} | {s['component_only_detected']} | {s['pairwise_detected']} |")
    report += ['', '## 서로 다른 출처의 자연어 명세와 정형 명세', '',
               '출처 S1–S9는 프로토콜에 작성한 서로 다른 합성 문서다. 실제 법규·운영자 문서를 수집한 결과가 아니다. '
               '아래 문장은 공급된 구조화 매개변수를 설명하기 위한 템플릿이며 자동 자연어 해석·검증 결과가 아니다. '
               '시간은 별도 표시가 없으면 ms, 좌표는 mm, 속도는 mm/s다.', '']
    for family in protocol['families']:
        example = next(c for c, row in zip(cases, rows) if c['family'] == family and row['full_status'] == 'UNSAT')
        report += [f'### {family}: {example["id"]}', '',
                   '고정 맥락: ' + protocol['context_roles'][family] + '.',
                   '매개변수: `' + json.dumps(example['parameters']) + '`.', '',
                   '| 출처 ID / 역할 | 자연어 명세 | 정형 명세 |', '|---|---|---|']
        for c in example['constraints']:
            report.append(f"| {c['source_document']['document_id']}: {c['source_document']['title']} ({c['source_kind']}) | "
                          f"{c['natural_language']} | $ {c['formal_specification']} $ |")
    report += ['', '## 검사 결과', '',
               f"전체 {stats['queries']}개 질의, UNKNOWN {stats['unknown']}, 독립 판정 불일치 {stats['mismatches']}.",
               f"SAT 해 {stats['sat_witnesses']}개를 독립 수치 계산으로 확인했고 잘못된 해는 {stats['invalid_witnesses']}개다.",
               f"전체 모순 {stats['full_unsat']}개 모두 고정 맥락에 대한 부분집합 최소 모순 그룹을 확인했고, "
               f"그중 {stats['pairwise_sat_full_unsat']}개는 모든 두 조건 조합이 SAT다. 경계 수정 대조 {repairs}개는 SAT다.", '',
               '## 해석과 범위', '',
               '진입 의무가 없는 대조군에서는 두 진입 제한을 기다림으로 만족할 수 있다. '
               '따라서 안전 제한과 진행 의무를 구분하고 맥락에 명시해야 한다. '
               'UNSAT는 지정된 맥락에서 요구사항들을 함께 만족할 수 없다는 뜻이며 어느 출처가 틀렸는지는 결정하지 않는다. '
               '최소 모순 그룹은 고정 맥락에 대한 제약 그룹 단위이며, 최소 크기의 유일한 원인이나 현실 사고의 원인이라는 뜻이 아니다. '
               '속도 과제는 일정 속도 가정이고 위치 유지는 표본 좌표 검사이며 연속시간 차량 안전을 보장하지 않는다. '
               '여러 법규의 자동 추출, 법적 예외 보존, CNL의 조합 의미, 학습 행동 개선은 평가하지 않는다.', '',
               '재현: `runtime/alpamayo/ar1_venv/bin/python '
               'projects/04-guardsynth-coc/experiments/paper1_cnl_learning/constraint_composition.py '
               '--run-id <unused-run-id>`', '']
    (target / 'REPORT_KO.md').write_text('\n'.join(report))
    manifest.update(status='COMPLETE', completed_at=datetime.now(timezone.utc).isoformat(),
                    output_hashes={p.name: digest(p) for p in target.iterdir() if p.name != 'RUN_MANIFEST.json'})
    dump(target / 'RUN_MANIFEST.json', manifest)
    print(json.dumps(dict(output=str(target), **result), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    run(parser.parse_args().run_id)
