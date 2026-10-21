"""Manually grounded policy/assumption compatibility cases for guardsynth-coc.

These are restricted authored scenarios, not accident reconstructions. Core/SMT
execution is imported unchanged; source review and numeric references live here.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations, product
import json
from pathlib import Path
import sys

import constraint_composition as synthetic

ROOT = synthetic.ROOT
lit, var, binary = synthetic.lit, synthetic.var, synthetic.binary
conjunction, clause = synthetic.conjunction, synthetic.clause
PROTOCOL = Path(__file__).with_name('document_grounded_composition_protocol_v0_1.json')
OUTPUT = synthetic.OUTPUT


def negate(formula):
    return dict(op='not', arg=formula)


def disjunction(items):
    return dict(op='or', args=items)


def stopping_mm(speed, deceleration):
    return Fraction(1000 * speed * speed, 2 * deceleration)


def ceil(value):
    return -(-value.numerator // value.denominator)


def build_case(family, p):
    groups, context = [], []
    def add(name, formula, source, role, natural, formal):
        groups.append(dict(id=name, source_id=source, source_kind=role,
                           natural_language=natural, formal_specification=formal,
                           clauses=[clause(name, formula, source)], source_refs=[source]))
    def assume(name, formula):
        context.append(clause(name, formula, 'authored:context/' + name))
    if family == 'suppression':
        declarations = [('brake_ms', 'INT'), ('stop_mm', 'INT')]
        assume('nonnegative_brake', binary('ge', var('brake_ms'), lit(0)))
        assume('nonnegative_stop', binary('ge', var('stop_mm'), lit(0)))
        add('suppression', binary('ge', var('brake_ms'), lit(p['delay_ms'])),
            'ntsb2019' if p['delay_ms'] else 'authored:delay_removal_control',
            'DOCUMENTED_POLICY_BRANCH' if p['delay_ms'] else 'AUTHORED_CONTROL',
            f"In the persistent-hazard/no-takeover/no-evasion branch, braking begins no earlier than {p['delay_ms']} ms after recognition.",
            rf"t_b\ge {p['delay_ms']}/1000")
        # Exact integer cross-multiplication of x >= v*t + v^2/(2*a).
        v, a = p['speed_m_s'], p['deceleration_m_s2']
        add('braking_model', binary('ge', binary('mul', lit(2 * a), var('stop_mm')),
                binary('add', binary('mul', lit(2 * a * v), var('brake_ms')), lit(1000 * v * v))),
            'authored:constant_deceleration', 'MODELING_ASSUMPTION',
            'Assume constant speed until braking and constant deceleration afterwards on a level road; no evasive path.',
            r"x_{stop}\ge v t_b+v^2/(2a)")
        add('avoidance_goal', binary('le', var('stop_mm'), lit(p['obstacle_mm'])),
            'authored:avoidance_goal', 'AUTHORED_REQUIREMENT',
            f"For this hypothetical state, stop within {p['obstacle_mm']} mm of recognition.",
            rf"x_{{stop}}\le {p['obstacle_mm']}/1000")
    elif family == 'yellow':
        declarations = [('stop', 'BOOL')]
        assume('two_action_partition', disjunction([var('stop'), negate(var('stop'))]))
        v, a, d = p['speed_m_s'], p['deceleration_m_s2'], p['distance_mm']
        # stop => d >= v*rho + v^2/(2a); proceed => d <= v*Y.
        add('nominal_stop', binary('implies', var('stop'),
                binary('ge', lit(2 * a * d), lit(2 * a * v * p['reaction_ms'] + 1000 * v * v))),
            'fhwa2009', 'DOCUMENT_INFORMED_MODEL',
            'The stop branch must reach rest before the stop line under the declared reaction time and nominal deceleration.',
            r"b\Rightarrow d\ge v\rho+v^2/(2a)")
        add('entry_before_red', binary('implies', negate(var('stop')),
                binary('le', lit(d), lit(v * p['yellow_ms']))),
            'fhwa2008', 'DOCUMENT_INFORMED_MODEL',
            'The constant-speed proceed branch must reach the stop line by the yellow endpoint in this closed-boundary timing abstraction.',
            r"\neg b\Rightarrow d\le vY")
    elif family == 'interlock':
        flags = ['door', 'park', 'parking_brake', 'airbag']
        declarations = [(name, 'BOOL') for name in flags + ['autonomous_drive']]
        for name in flags:
            assume('observed_' + name, binary('eq', var(name), lit(p[name])))
        add('interlock', binary('implies', disjunction([var(n) for n in flags]),
                               negate(var('autonomous_drive'))),
            'waymo2026', 'MANUFACTURER_POLICY',
            'An open door, Park, applied parking brake, or deployed airbag prevents autonomous driving.',
            r"(o\lor p\lor k\lor a)\Rightarrow\neg m_{auto}")
        add('candidate_request', binary('eq', var('autonomous_drive'), lit(p['drive'])),
            'authored:candidate_request', 'AUTHORED_CANDIDATE',
            'Evaluate a candidate that ' + ('drives autonomously.' if p['drive'] else 'does not drive autonomously.'),
            r"m_{auto}=" + (r"\top" if p['drive'] else r"\bot"))
    elif family == 'exception':
        declarations = [(n, 'BOOL') for n in ['stationary', 'necessary', 'clear', 'cross']]
        for name in ['stationary', 'necessary', 'clear']:
            assume('observed_' + name, binary('eq', var(name), lit(p[name])))
        exception = conjunction([var(n) for n in ['stationary', 'necessary', 'clear']])
        formula = binary('implies', var('cross'), exception) if p['faithful'] else negate(var('cross'))
        add('crossing_rule', formula, 'highway129',
            'RESTRICTED_DOCUMENT_RULE' if p['faithful'] else 'DELIBERATE_OMITTED_EXCEPTION_FAULT',
            ('With the nearer line solid and other exceptions absent, crossing requires a stationary vehicle, necessity, and a clear road.'
             if p['faithful'] else 'Faulty transcription: prohibit crossing unconditionally, omitting the stationary-vehicle exception.'),
            r"c\Rightarrow(q\land n\land f)" if p['faithful'] else r"\neg c")
        add('candidate_request', binary('eq', var('cross'), lit(p['cross'])),
            'authored:candidate_request', 'AUTHORED_CANDIDATE',
            'Evaluate a candidate that ' + ('crosses the line.' if p['cross'] else 'does not cross the line.'),
            r"c=" + (r"\top" if p['cross'] else r"\bot"))
    else:
        raise ValueError(family)
    refs = sorted({r for g in groups for r in g['source_refs']}
                  | {r for c in context for r in c['source_refs']} | {'authored:context'})
    raw = dict(grammar_version='eblc-core-v0.1', model_id=family, horizon=2,
               declarations=[dict(name=n, sort=s, time_varying=False, unit='1' if s == 'INT' else None,
                  enum_name=None, enum_values=[], frame=None, source_refs=['authored:context']) for n, s in declarations],
               clauses=context, queries=[], source_refs=refs,
               claim_scope='DOCUMENT_GROUNDED_AUTHORED_SCENARIOS_NOT_OPERATIONAL_VALIDATION')
    return dict(family=family, parameters=p, constraints=groups, context_model=raw)


def generate_cases(protocol):
    cases = []
    def add(family, **p):
        case = build_case(family, p)
        case['id'] = f'{family}-{sum(c["family"] == family for c in cases):03d}'
        cases.append(case)
    grid = protocol['grids']['suppression']
    for v, a, delay, offset in product(grid['speed_m_s'], grid['deceleration_m_s2'],
                                      grid['delay_ms'], grid['distance_mm_relative_to_delayed_stop']):
        add('suppression', speed_m_s=v, deceleration_m_s2=a, delay_ms=delay,
            obstacle_mm=ceil(stopping_mm(v, a)) + v * delay + offset)
    for v, a, delay in product(grid['speed_m_s'], grid['deceleration_m_s2'], grid['delay_ms']):
        add('suppression', speed_m_s=v, deceleration_m_s2=a, delay_ms=delay,
            obstacle_mm=ceil(stopping_mm(v, a)) + v * 500)
    grid = protocol['grids']['yellow']
    for v, y in product(grid['speed_m_s'], grid['yellow_ms']):
        stop = v * grid['reaction_ms'] + stopping_mm(v, grid['nominal_deceleration_m_s2'])
        reach = Fraction(v * y)
        distances = {n for x in [stop, reach] for n in [x.numerator // x.denominator - 1, ceil(x), ceil(x) + 1]}
        distances.add(int((stop + reach) / 2))
        if v == 15 and y == 3000:
            distances.add(50000)
        for d in sorted(distances):
            add('yellow', speed_m_s=v, deceleration_m_s2=grid['nominal_deceleration_m_s2'],
                reaction_ms=grid['reaction_ms'], yellow_ms=y, distance_mm=d)
    for door, park, brake, airbag, drive in product([False, True], repeat=5):
        add('interlock', door=door, park=park, parking_brake=brake, airbag=airbag, drive=drive)
    for stationary, necessary, clear, cross, faithful in product([False, True], repeat=5):
        add('exception', stationary=stationary, necessary=necessary, clear=clear, cross=cross, faithful=faithful)
    return cases


def expected(case, subset):
    p, family = case['parameters'], case['family']
    ids = {case['constraints'][i]['id'] for i in subset}
    if family == 'suppression':
        minimum_brake = p['delay_ms'] if 'suppression' in ids else 0
        feasible = not {'braking_model', 'avoidance_goal'} <= ids or (
            p['speed_m_s'] * minimum_brake + stopping_mm(p['speed_m_s'], p['deceleration_m_s2']) <= p['obstacle_mm'])
    elif family == 'yellow':
        stop_ok = 'nominal_stop' not in ids or p['distance_mm'] >= (
            p['speed_m_s'] * p['reaction_ms'] + stopping_mm(p['speed_m_s'], p['deceleration_m_s2']))
        proceed_ok = 'entry_before_red' not in ids or p['distance_mm'] <= p['speed_m_s'] * p['yellow_ms']
        feasible = stop_ok or proceed_ok
    elif family == 'interlock':
        blocked = any(p[n] for n in ['door', 'park', 'parking_brake', 'airbag'])
        feasible = not {'interlock', 'candidate_request'} <= ids or not (p['drive'] and blocked)
    else:
        allowed = p['faithful'] and all(p[n] for n in ['stationary', 'necessary', 'clear'])
        feasible = not {'crossing_rule', 'candidate_request'} <= ids or not p['cross'] or allowed
    return 'SAT' if feasible else 'UNSAT'


def valid_witness(case, subset, w):
    p, f = case['parameters'], case['family']
    ids = {case['constraints'][i]['id'] for i in subset}
    if f == 'suppression':
        return (w['brake_ms'] >= 0 and w['stop_mm'] >= 0
            and ('suppression' not in ids or w['brake_ms'] >= p['delay_ms'])
            and ('braking_model' not in ids or w['stop_mm'] >=
                 p['speed_m_s'] * w['brake_ms'] + stopping_mm(p['speed_m_s'], p['deceleration_m_s2']))
            and ('avoidance_goal' not in ids or w['stop_mm'] <= p['obstacle_mm']))
    if f == 'yellow':
        return (('nominal_stop' not in ids or not w['stop'] or p['distance_mm'] >=
                 p['speed_m_s'] * p['reaction_ms'] + stopping_mm(p['speed_m_s'], p['deceleration_m_s2']))
            and ('entry_before_red' not in ids or w['stop'] or p['distance_mm'] <= p['speed_m_s'] * p['yellow_ms']))
    if f == 'interlock':
        names = ['door', 'park', 'parking_brake', 'airbag']
        return (all(w[n] == p[n] for n in names)
            and ('interlock' not in ids or not any(w[n] for n in names) or not w['autonomous_drive'])
            and ('candidate_request' not in ids or w['autonomous_drive'] == p['drive']))
    names = ['stationary', 'necessary', 'clear']
    return (all(w[n] == p[n] for n in names)
        and ('crossing_rule' not in ids or not w['cross'] or (p['faithful'] and all(w[n] for n in names)))
        and ('candidate_request' not in ids or w['cross'] == p['cross']))


def evaluate(case):
    raw = deepcopy(case['context_model'])
    subsets = [s for size in range(len(case['constraints']) + 1)
               for s in combinations(range(len(case['constraints'])), size)]
    for k, subset in enumerate(subsets):
        raw['queries'].append(dict(id=f'subset_{k}', expected=expected(case, subset), classification='CONSISTENCY',
            formula=conjunction([c['formula'] for i in subset for c in case['constraints'][i]['clauses']]),
            source_refs=[r for i in subset for r in case['constraints'][i]['source_refs']] or raw['source_refs'],
            description='Fixed authored context plus selected document/model/candidate groups.'))
    compiled = synthetic.compile_core_model(synthetic.parse_core_model(raw))
    queries = []
    for subset, result in zip(subsets, synthetic.check_queries(compiled)['results']):
        w = None if result['witness'] is None else {s['declaration']: result['witness'][s['smt_symbol']]
                                                  for s in compiled.symbol_table['symbols']}
        result.update(case_id=case['id'], selected=list(subset), witness=w,
                      witness_valid=None if w is None else valid_witness(case, subset, w))
        queries.append(result)
    cores = [q['selected'] for q in queries if q['status'] == 'UNSAT' and all(
        r['status'] == 'SAT' for r in queries if set(r['selected']) < set(q['selected']))]
    return dict(case_id=case['id'], family=case['family'], full_status=queries[-1]['status'],
                context_sat=queries[0]['status'] == 'SAT',
                components_sat=all(q['status'] == 'SAT' for q in queries if len(q['selected']) == 1),
                pairs_sat=all(q['status'] == 'SAT' for q in queries if len(q['selected']) == 2),
                minimal_conflict_groups=[[case['constraints'][i]['id'] for i in c] for c in cores],
                queries=queries, core_model=raw)


def run(run_id):
    protocol = json.loads(PROTOCOL.read_text())
    cases = generate_cases(protocol)
    assert len(cases) == protocol['planned_case_count'], len(cases)
    target = OUTPUT / run_id
    target.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__), PROTOCOL, Path(synthetic.__file__), Path(synthetic.entry.__file__),
              Path(synthetic.hold.__file__), ROOT / 'cli/solver_runtime.py',
              ROOT / 'projects/04-guardsynth-coc/tests/unit/test_document_grounded_composition.py',
              ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/core_ir.py',
              ROOT / 'platforms/eblc-bcv/src/guard_synth_eblc/smt_compiler.py']
    manifest = dict(project_id='guardsynth-coc', task_id=protocol['task_id'], run_id=run_id,
        status='INPUTS_FROZEN', created_at=datetime.now(timezone.utc).isoformat(),
        input_hashes={str(p.relative_to(ROOT)): synthetic.digest(p) for p in inputs},
        runtime=dict(python=sys.version, solver=synthetic.configure_project_z3(ROOT).manifest()))
    synthetic.dump(target / 'RUN_MANIFEST.json', manifest)
    synthetic.dump(target / 'protocol.json', protocol)
    synthetic.dump(target / 'SOURCE_CATALOG.json', protocol['sources'])
    (target / 'cases.jsonl').write_text(''.join(json.dumps(c) + '\n' for c in cases))
    rows = [evaluate(c) for c in cases]
    stats = synthetic.summarize(rows)
    assert stats['queries'] == protocol['planned_subset_queries'], stats
    assert stats['unknown'] == stats['mismatches'] == stats['invalid_witnesses'] == 0, stats
    assert stats['all_components_sat'] == len(cases), stats
    families = {f: synthetic.summarize([r for r in rows if r['family'] == f]) for f in protocol['grids']}
    controls = {}
    for name, predicate in [
        ('suppression_only_incompatible', lambda c: c['family'] == 'suppression' and c['parameters']['delay_ms'] == 1000
           and c['parameters']['obstacle_mm'] >= stopping_mm(c['parameters']['speed_m_s'], c['parameters']['deceleration_m_s2'])),
        ('hold_requests', lambda c: c['family'] == 'interlock' and not c['parameters']['drive']),
        ('exception_preserved', lambda c: c['family'] == 'exception' and c['parameters']['faithful'] and c['parameters']['cross']
           and all(c['parameters'][n] for n in ['stationary', 'necessary', 'clear'])),
        ('no_cross_requests', lambda c: c['family'] == 'exception' and not c['parameters']['cross'])]:
        selected = [r for c, r in zip(cases, rows) if predicate(c)]
        controls[name] = dict(cases=len(selected), sat=sum(r['full_status'] == 'SAT' for r in selected),
                              unsat=sum(r['full_status'] == 'UNSAT' for r in selected))
    result = dict(project_id='guardsynth-coc', task_id=protocol['task_id'], status='COMPLETE',
                  aggregate=stats, families=families, controls=controls, claim_scope=protocol['claim_scope'])
    synthetic.dump(target / 'RESULT.json', result)
    (target / 'queries.jsonl').write_text(''.join(json.dumps(q) + '\n' for r in rows for q in r['queries']))
    (target / 'compositions.jsonl').write_text(''.join(json.dumps({k: v for k, v in r.items() if k != 'queries'}) + '\n' for r in rows))
    write_report(target, protocol, cases, rows, result)
    manifest.update(status='COMPLETE', completed_at=datetime.now(timezone.utc).isoformat(),
                    output_hashes={p.name: synthetic.digest(p) for p in target.iterdir() if p.name != 'RUN_MANIFEST.json'})
    synthetic.dump(target / 'RUN_MANIFEST.json', manifest)
    print(json.dumps(dict(output=str(target), **result), indent=2))


def write_report(target, protocol, cases, rows, result):
    lines = ['# 실제 문서에 근거한 제약 조합 진단', '', '소유 프로젝트: `guardsynth-coc`', '',
        '599 ms 운영자 기한은 실제 문서의 조건이 아니므로, 앞선 합성 경계 검사와 구분하여 다음 사례를 구성했다. '
        '공식 문서 8건의 원문과 적용 범위를 검토했고, UNECE 문서 2건은 직접 접근이 막혀 실행 근거에서 제외했다. '
        '실제 정책의 일부와 명시한 가정으로 구성한 진단이며, 사고 재현·자연 발생 빈도·주행 모델 성능 실험이 아니다.', '',
        '## 출처 검토', '', '| ID / 문서 | 확인한 근거와 위치 | 채택 범위 |', '|---|---|---|']
    for key, source in protocol['sources'].items():
        lines.append(f"| {key}: [{source['title']}]({source['url']}) | {source.get('verified_paraphrase', '직접 원문 확인 미완료')} / {source['locator']} | {source['use']}: {source['scope']} |")
    lines += ['', '## 서로 다른 출처 역할의 자연어·정형 명세', '',
        '문서의 조건, 작성한 상태 입력/후보, 모델링 가정, 검사 목표를 따로 기록한다. '
        '서로 다른 발행기관의 실제 정책들이 그 자체로 모순이라는 주장이 아니다. '
        '아래 수식은 SI 단위로 표시하며 실행은 정수 ms/mm 및 분모 제거를 사용한다. '
        '정지 거리는 mm 격자로 위쪽 반올림하여 경계에서 낙관적인 허용을 만들지 않는다.', '']
    for family in protocol['grids']:
        example = next((c for c, r in zip(cases, rows) if c['family'] == family and r['full_status'] == 'UNSAT'
                       and (family != 'suppression' or c['parameters']['delay_ms'] == 1000)
                       and (family != 'exception' or all(c['parameters'][n] for n in ['stationary', 'necessary', 'clear']))), None)
        lines += [f'### {family}', '', '가정 및 상태: `' + json.dumps(example['parameters']) + '`.', '',
                  '| 출처 / 역할 | 자연어 명세 | 정형 명세 |', '|---|---|---|']
        for group in example['constraints']:
            lines.append(f"| {group['source_id']} / {group['source_kind']} | {group['natural_language']} | ${group['formal_specification']}$ |")
    lines += ['', '## 결과', '', '| 계열 | 사례 | SAT | UNSAT | 질의 | 모든 쌍 SAT인 전체 모순 |', '|---|---:|---:|---:|---:|---:|']
    for family, s in result['families'].items():
        lines.append(f"| {family} | {s['cases']} | {s['full_sat']} | {s['full_unsat']} | {s['queries']} | {s['pairwise_sat_full_unsat']} |")
    s = result['aggregate']
    lines += ['', f"총 {s['cases']}개 구성, {s['queries']}개 질의. UNKNOWN {s['unknown']}, 독립 판정 불일치 {s['mismatches']}, "
              f"잘못된 SAT 해 {s['invalid_witnesses']}/{s['sat_witnesses']}.", '',
        '## 사례별 해석', '',
        '- **제동 억제:** 1초 정책, 일정 감속 가정, 정지 거리 목표를 함께 검사한다. 지연 없이도 목표를 달성할 수 없는 상태를 따로 포함하므로 모든 모순을 지연 탓으로 세지 않는다. '
        '문서의 실제 Tempe 상태에서는 이미 설계 제동 한계로 회피가 어려웠다는 설명을 유지한다. 0초 지연 대조는 가상 상태의 비교이지 실제 사고 회피 주장에 쓰지 않는다.',
        '- **황색 신호:** 선택지가 일정 속도 진행/명목 감속 정지로 제한될 때 두 선택 모두 배제되는 구간을 확인한다. 실제 긴급 제동·가속·회피 가능성까지 배제한 결과가 아니다. '
        '노란 신호 종료 시각의 등호는 닫힌 경계 계산 관례이며 실제 법률상 황색/적색 순간의 해석으로 주장하지 않는다.',
        '- **이동 차단:** 제조사 인터록과 이동 후보의 양립 가능성을 검사한다. 홀드 후보는 16개 상태 모두 SAT다. 차량의 굴러감/견인까지 금지하는 명세로 확대하지 않는다.',
        '- **예외 보존:** 모든 예외 조건이 참일 때 충실한 명세는 횡단 후보를 허용하고, 예외를 삭제한 변형은 이를 배제한다. '
        '횡단을 요구하지 않는 후보는 둘 다 SAT다. 원래 도로 규칙 간 모순이 아니라 누락된 예외의 효과다.', '',
        '## 기록의 한계', '',
        'SOURCE_CATALOG.json은 사람이 확인한 URL·판본·문단·해석 범위를 보관한다. 원문 PDF의 바이트 복사본과 해시를 확보한 보존본은 아니다. '
        '법규의 모든 조항, 자연어 자동 추출, 현장 상태의 타당성, 연속시간 안전은 검사하지 않는다. '
        '출처 종류가 다른 입력들을 함께 검사할 수 있음을 보이며, 실제 운영 로그에서 충돌 정책을 발견했다는 뜻은 아니다.', '']
    (target / 'REPORT_KO.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    run(parser.parse_args().run_id)
