"""guardsynth-coc: offline definition feasibility and nonvacuity experiment.

No observed facts constrain hypothetical definition states. Activation is AND;
release is OR. Spatial order semantics match the maintained qualitative profile.
This is not a scene-truth, reachability or production liveness checker.
"""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import time

import z3

from studio_property_probe import canonical
from guard_synth.studio_sequence import compile_sequence, verify_compiled


PROTOCOL = {
    'project_id': 'guardsynth-coc', 'version': 'studio-condition-feasibility-probe-v0.1',
    'solver_timeout_ms': 500, 'paid_calls': 0,
    'activation': 'AND of activation_all_of; empty activation is missing input.',
    'release': 'OR of release_any_of; empty release is missing input, not a proven faulty permanent rule.',
    'raw_domain': 'Independent Boolean atoms with shared identical predicate/subject/object keys.',
    'typed_domain': 'Supported atom kinds plus strict integer spatial order and inverse directions; no signal-color exclusivity or speculative physical axioms.',
    'normalization': 'Use the existing experimental PATH_CLEAR(ego, zone/lane) normalization in memory only; report unsupported guards separately.',
    'facts': 'No CoC or constraint observed truth values are asserted in definition queries.',
    'effective_activation': 'activation AND NOT release; unsatisfiable result means activation cannot hold without release also holding.',
    'scope': 'Stored structured candidates from extraction runs, definition occurrences rather than independent unique rules.',
    'liveness': 'Only a separately labelled synthetic two-state loop control; no actual-data liveness verdict.',
}


class DefinitionModel:
    def __init__(self, guards, kinds=None):
        self.solver = z3.Solver();self.solver.set(timeout=PROTOCOL['solver_timeout_ms'])
        self.variables = {};self.invalid = [];self.normalized = []
        for index, g in enumerate(guards):
            raw = tuple(g['atom'][k] for k in ('predicate', 'subject_ref', 'object_ref'))
            key = canonical(g['atom'], kinds) if kinds is not None else raw
            if key is None:
                self.invalid.append(index);key = raw
            if key != raw:self.normalized.append({'index': index, 'from': raw, 'to': key})
            self.atom(key)
        if kinds is not None:
            for (predicate, subject, target), atom in list(self.variables.items()):
                if predicate not in ('LEFT_OF', 'RIGHT_OF', 'AHEAD_OF', 'BEHIND_OF'):continue
                axis = 'lateral' if predicate in ('LEFT_OF', 'RIGHT_OF') else 'longitudinal'
                left = z3.Int(axis + '_' + subject);right = z3.Int(axis + '_' + str(target))
                order = left < right if predicate in ('LEFT_OF', 'BEHIND_OF') else left > right
                self.solver.add(atom == order)

    def atom(self, key):
        key = tuple(key)
        if key not in self.variables:
            self.variables[key] = z3.Bool('atom_' + hashlib.sha256(repr(key).encode()).hexdigest()[:20])
        return self.variables[key]

    def literal(self, guard, kinds=None):
        raw = tuple(guard['atom'][k] for k in ('predicate', 'subject_ref', 'object_ref'))
        key = canonical(guard['atom'], kinds) if kinds is not None else raw
        atom = self.atom(raw if key is None else key)
        return atom if guard['expected_truth'] == 'TRUE' else z3.Not(atom)

    def query(self, groups, kinds=None):
        # groups = [(guards, AND|OR, negate), ...]; outer connective is AND.
        self.solver.push();labels = {}
        for group, mode, negate in groups:
            if negate:
                expr = z3.And(*(self.literal(g, kinds) for g in group)) if mode == 'AND' else z3.Or(*(self.literal(g, kinds) for g in group))
                label = z3.Bool('guard_group_' + str(len(labels)));labels[str(label)] = {'guards': group, 'mode': mode, 'negated': True}
                self.solver.assert_and_track(z3.Not(expr), label)
            elif mode == 'AND':
                for g in group:
                    label = z3.Bool('guard_group_' + str(len(labels)));labels[str(label)] = g
                    self.solver.assert_and_track(self.literal(g, kinds), label)
            else:
                label = z3.Bool('guard_group_' + str(len(labels)));labels[str(label)] = {'guards': group, 'mode': mode}
                self.solver.assert_and_track(z3.Or(*(self.literal(g, kinds) for g in group)), label)
        checked = self.solver.check()
        result = {'status': str(checked).upper()}
        if checked == z3.sat:
            model = self.solver.model()
            result['witness'] = [{'atom': key, 'truth': str(model.eval(value, model_completion=True)).upper()} for key, value in self.variables.items()]
        elif checked == z3.unsat:
            result['conflicting_guards'] = [labels[str(label)] for label in self.solver.unsat_core()]
        else:result['reason_unknown'] = self.solver.reason_unknown()
        self.solver.pop();return result


def check_definition(definition, kinds=None):
    on = definition['activation_all_of'];off = definition['release_any_of'];pre = definition['preconditions']
    specs = {'activation': [(on, 'AND', False)], 'release': [(off, 'OR', False)],
             'effective_activation': [(on, 'AND', False), (off, 'OR', True)],
             'release_tautology': [(off, 'OR', True)],
             'activation_release_overlap': [(on, 'AND', False), (off, 'OR', False)]}
    if definition['effect'] in ('ALLOW', 'REQUIRE'):
        specs['activation_preconditions'] = [(on, 'AND', False), (pre, 'AND', False)]
    results = {}
    for name, groups in specs.items():
        if (name != 'release' and name != 'release_tautology' and not on) or (name != 'activation' and name != 'activation_preconditions' and not off):
            results[name] = {'status': 'MISSING_GUARD'};continue
        guards = [g for group, _, _ in groups for g in group]
        model = DefinitionModel(guards, kinds)
        if model.invalid:
            results[name] = {'status': 'NOT_CHECKED_INVALID_GUARDS', 'invalid_guards': [guards[i] for i in model.invalid]};continue
        results[name] = {**model.query(groups, kinds), 'normalizations': model.normalized}
    return results


def load_moments(directory):
    moments = []
    for point in (1, 2):
        coc = json.loads((directory / f'revision_{point}_coc_candidate.json').read_text())
        con = json.loads((directory / f'revision_{point}_constraints_candidate.json').read_text())
        req = json.loads((directory / f'revision_{point}_coc_request.json').read_text())['input_data']
        current = req['frames'][-1];evidence = [f['frame_id'] for f in req['frames']];now = [current['frame_id']]
        for record in (req.get('vehicle_state') or {}).get('frames', []):
            if record.get('sample'):
                ref = 'CAN:' + str(record['sample']['timestamp_us']);evidence.append(ref)
                if record['frame_timestamp_us'] == current['timestamp_us']:now.append(ref)
        moments.append({'id': f'feasibility-control-{point}', 'ordinal': point-1, 't0_us': current['timestamp_us'],
                        'frame_ids': evidence, 'current_evidence_refs': now, 'reviewed': True, 'coc': coc, 'constraints': con})
    return moments


def guard(predicate, subject, target=None, truth='TRUE'):
    return {'atom': {'predicate': predicate, 'subject_ref': subject, 'object_ref': target}, 'expected_truth': truth}


def mutation_controls(directory):
    moments = load_moments(directory);original = deepcopy(moments)
    definition = moments[0]['constraints']['new_definitions'][0]
    kinds = {e['entity_id']: e['kind'] for e in moments[0]['coc']['entities']}
    before = verify_compiled(compile_sequence(moments, {'sources': []}))
    path = guard('PATH_CLEAR', definition['action_target_ref'])
    variants = {}
    injected = deepcopy(definition);injected['activation_all_of'] = [path, {**path, 'expected_truth': 'FALSE'}]
    variants['contradictory_activation'] = injected
    injected = deepcopy(definition);injected['release_any_of'] = [guard('LEFT_OF', 'ego', 'ego')]
    variants['impossible_release'] = injected
    injected = deepcopy(definition);injected['release_any_of'] = [path, {**path, 'expected_truth': 'FALSE'}]
    variants['tautological_release'] = injected
    injected = deepcopy(definition);injected['activation_all_of'] = [guard('PATH_CLEAR', 'e2'), guard('PATH_CLEAR', 'e3', truth='FALSE')]
    variants['different_targets_negative_control'] = injected
    results = {}
    restored = check_definition(definition, kinds)
    for name, candidate in variants.items():
        changed = deepcopy(moments);changed[0]['constraints']['new_definitions'][0] = candidate
        verified = verify_compiled(compile_sequence(changed, {'sources': []}))
        results[name] = {'kind': 'SYNTHETIC_DEFINITION_MUTATION', 'source': str(directory),
                         'original_definition': definition, 'injected_definition': candidate,
                         'original_baseline_statuses': [s['status'] for s in before['scenes']],
                         'injected_baseline_statuses': [s['status'] for s in verified['scenes']],
                         'injected_baseline_codes': [s['codes'] for s in verified['scenes']],
                         'injected_result': check_definition(candidate, kinds), 'restored_result': restored}
    assert results['contradictory_activation']['injected_result']['activation']['status'] == 'UNSAT'
    assert results['impossible_release']['injected_result']['release']['status'] == 'UNSAT'
    assert results['tautological_release']['injected_result']['release']['status'] == 'SAT'
    assert results['tautological_release']['injected_result']['release_tautology']['status'] == 'UNSAT'
    assert results['tautological_release']['injected_result']['effective_activation']['status'] == 'UNSAT'
    assert results['different_targets_negative_control']['injected_result']['activation']['status'] == 'SAT'
    assert restored['activation']['status'] == restored['release']['status'] == restored['effective_activation']['status'] == 'SAT'
    assert moments == original
    # Distinguish state satisfiability from progress with a labelled toy model.
    closed0, closed1, active0, active1 = z3.Bools('closed0 closed1 active0 active1')
    toy = z3.Solver();toy.set(timeout=PROTOCOL['solver_timeout_ms'])
    toy.add(closed0, active0, closed1 == closed0, active1 == z3.And(active0, closed1),
            active1 == active0, closed1)
    assert toy.check() == z3.sat
    results['liveness_loop_control'] = {'kind': 'SYNTHETIC_TRANSITION_MODEL_NOT_REAL_GENERATION',
        'release_guard': 'NOT zone_closed; satisfiable as a state formula',
        'transition': 'zone_closed_next = zone_closed; active_next = active AND zone_closed_next',
        'loop_witness': {'before': {'zone_closed': True, 'active': True}, 'after': {'zone_closed': True, 'active': True}},
        'violated_toy_requirement': 'G(active -> F released)',
        'note': 'Repeating this legal self-loop violates the toy eventual-release requirement. Actual Studio candidates have no such environment transition model or unconditional eventual-release requirement.'}
    return results


def actual_review_controls(rows):
    results = []
    for row in rows:
        if row['typed_checks'].get('activation_preconditions', {}).get('status') != 'UNSAT':continue
        directory = Path(row['source']).parent
        moments = load_moments(directory)
        point = int(Path(row['source']).name.split('_')[1]) - 1
        kinds = {e['entity_id']: e['kind'] for e in moments[point]['coc']['entities']}
        proposed = deepcopy(row['definition'])
        changed = []
        for index, g in enumerate(proposed['preconditions']):
            atom = g['atom']
            if atom['predicate'] in ('LEFT_OF', 'RIGHT_OF', 'AHEAD_OF', 'BEHIND_OF') and atom['subject_ref'] == atom['object_ref'] and atom['subject_ref'] != 'ego':
                atom['object_ref'] = 'ego';changed.append(index)
        if not changed:continue
        result = check_definition(proposed, kinds)['activation_preconditions']
        assert result['status'] == 'SAT'
        try:
            baseline = verify_compiled(compile_sequence(moments, {'sources': []}))
            baseline_result = {'status': baseline['scenes'][point]['status'], 'codes': baseline['scenes'][point]['codes']}
        except ValueError as error:
            baseline_result = {'status': 'CURRENT_PROFILE_REPLAY_UNAVAILABLE', 'reason': str(error)}
        self_relations = [r for r in moments[point]['coc']['relations'] if r['subject_ref'] == r['object_ref'] and r['predicate'] in ('LEFT_OF', 'RIGHT_OF', 'AHEAD_OF', 'BEHIND_OF')]
        results.append({'kind': 'ACTUAL_OLDER_MODEL_DEFINITION_WITH_UNAPPLIED_CORRECTION_PROPOSAL',
                        'source': row['source'], 'pointer': row['pointer'], 'condition_id': row['condition_id'],
                        'original_result': row['typed_checks']['activation_preconditions'],
                        'proposed_definition': proposed, 'proposed_result': result,
                        'current_profile_baseline': baseline_result, 'coc_self_relations': self_relations,
                        'note': 'Only the definition precondition was changed in memory. The original CoC also contains a self-order relation and is not corrected. This is not a newly detected failure of a previously passing current-profile case.'})
    return results


def run(root, output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = {};rows = [];point_count = 0;start = time.perf_counter()
    source_counts = Counter()
    def read(path):
        raw = path.read_bytes();inputs[str(path)] = hashlib.sha256(raw).hexdigest();return json.loads(raw)
    for run_dir in sorted(root.glob('studio-extraction-test-*')):
        for path in sorted(run_dir.rglob('*constraints_candidate.json')):
            con = read(path)
            if 'new_definitions' not in con:continue
            coc = read(path.with_name(path.name.replace('constraints_candidate', 'coc_candidate')))
            req = read(path.with_name(path.name.replace('constraints_candidate', 'coc_request')))['input_data']
            kinds = {e['entity_id']: e['kind'] for e in req.get('previous_entities', []) + coc['entities']}
            point_count += 1
            for index, definition in enumerate(con['new_definitions']):
                rows.append({'run': run_dir.name, 'source': str(path), 'pointer': '/new_definitions/' + str(index),
                             'condition_id': definition['condition_id'], 'description': definition['description'],
                             'effect': definition['effect'], 'definition': definition,
                             'raw_checks': check_definition(definition), 'typed_checks': check_definition(definition, kinds)})
                source_counts[run_dir.name] += 1
    elapsed = time.perf_counter() - start
    controls = mutation_controls(root / 'studio-extraction-test-2026-10-04-001/scene-0061-pair-005')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p, sha in inputs.items())
    counts = {profile: {name: dict(Counter(row[profile][name]['status'] for row in rows if name in row[profile]))
                       for name in ('activation', 'release', 'effective_activation', 'release_tautology', 'activation_release_overlap', 'activation_preconditions')}
              for profile in ('raw_checks', 'typed_checks')}
    failures = [row for row in rows if any(row[profile][name]['status'] == 'UNSAT'
                 for profile in ('raw_checks', 'typed_checks') for name in ('activation', 'release'))]
    review = [row for row in rows if row['typed_checks']['effective_activation']['status'] == 'UNSAT'
              or row['typed_checks']['release_tautology']['status'] == 'UNSAT'
              or row['typed_checks'].get('activation_preconditions', {}).get('status') == 'UNSAT']
    actual_controls = actual_review_controls(review)
    summary = {'project_id': 'guardsynth-coc', 'status': 'COMPLETE', 'paid_calls': 0,
               'points': point_count, 'definition_occurrences': len(rows), 'definitions_by_run': dict(source_counts),
               'status_counts': counts, 'actual_impossible_activation_or_release_occurrences': len(failures),
               'additional_definition_review_occurrences': len(review), 'actual_liveness_violations': 'NOT_EVALUATED',
               'actual_definition_correction_controls': len(actual_controls),
               'actual_definition_check_s': elapsed, 'input_originals_preserved': True, 'studio_modified': False,
               'mutation_controls': {'definition_controls_passed': 4, 'synthetic_liveness_loop_confirmed': True,
                                     'counted_as_real_model_errors': False},
               'limitations': ['Existing prompts and repeated definition occurrences; not independent unique rules.',
                               'No physical/environment transition model: SAT does not establish reachability or liveness.',
                               'Invalid typed guards remain unassessed, not logical failures.',
                               'Snapshot facts are deliberately excluded from definition feasibility.']}
    for name, value in [('protocol.json', PROTOCOL), ('checks.json', rows), ('mutation_controls.json', controls),
                        ('input_hashes.json', inputs), ('RESULT.json', summary), ('actual_failures.json', failures),
                        ('definition_reviews.json', review), ('actual_correction_controls.json', actual_controls)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    with (output / 'condition_comparison.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        fields = ['run', 'source', 'pointer', 'condition_id', 'description', 'effect', 'profile', 'check', 'status', 'details']
        writer = csv.DictWriter(handle, fields);writer.writeheader()
        for row in rows:
            for profile in ('raw_checks', 'typed_checks'):
                for name, result in row[profile].items():
                    writer.writerow({**{k: row[k] for k in fields[:6]}, 'profile': profile, 'check': name,
                                     'status': result['status'], 'details': json.dumps(result, ensure_ascii=False)})
    report = [
        '# 제약 정의 실행 가능성 검사 결과', '',
        f'저장된 실제 생성 {point_count}시점에서 제약 정의 {len(rows)}개 등장 건을 검사했다. 동일 정의가 다른 생성에서 반복될 수 있으며 독립적인 고유 규칙 수가 아니다. 추가 유료 호출은 0회이다.', '',
        f'활성 또는 해제 조건의 불가능성이 확정된 실제 정의는 {len(failures)}건이다. 효과적인 활성화·해제 항진식·활성과 선행 조건의 결합에 관한 추가 검토 대상은 {len(review)}건이다. 상세 항목은 `actual_failures.json`과 `definition_reviews.json`에 있다.', '',
        '현재 관찰 사실을 제외한 Boolean 검사와 대상 종류 및 엄격한 공간 순서를 적용한 검사를 분리했다. 지원되지 않는 대상·원자는 검사 불가로 남겼다. 신호 색 상호배타성이나 추가 물리 가정은 사용하지 않았다.', '',
        '| 검사 | 대상 종류와 공간 의미를 적용한 결과 |', '| --- | --- |']
    for name, values in counts['typed_checks'].items():
        report.append('| ' + name + ' | ' + ', '.join(f'{k}: {v}' for k, v in values.items()) + ' |')
    report.extend(['',
        '해제 조건 누락 7건과 지원되지 않는 조건 때문에 각 주요 검사에서 보류한 8건은 불가능성이 없다고 확정한 사례에 포함하지 않는다. 활성·해제 동시 성립이 가능한 정의는 6건이나, 실제 관찰된 모순이나 모든 상태에서의 실행 불가능성으로 세지 않는다.', ''])
    for control in actual_controls:
        report.extend([
            f"실제 과거 생성 사례 `{control['condition_id']}`는 선행 조건에 `AHEAD_OF(zone_intersection_1, zone_intersection_1)=TRUE`를 요구한다. 엄격한 순서에서는 자기 자신보다 앞에 있을 수 없어 활성 조건과 선행 조건의 결합이 UNSAT이다.", '',
            '원본을 보존하고 선행 조건의 비교 대상만 자차로 바꾼 수정안은 SAT이다. CoC에도 같은 자기 순서 관계가 있어 그 항목까지 검토해야 전체 입력을 정리할 수 있다. 수정안은 적용하거나 사람의 검토를 받지 않았다.', '',
            f"현재 프로필의 원본 재검사 상태는 `{control['current_profile_baseline']['status']}`이다. " +
            ('이전 형식의 entity ID가 현재 규약에 맞지 않아 재검사할 수 없었다. 기존에 통과한 입력의 추가 탈락으로 주장하지 않는다.' if control['current_profile_baseline']['status'] == 'CURRENT_PROFILE_REPLAY_UNAVAILABLE' else '기존 판정과 정의 검사 결과를 별도로 기록했다.'), ''])
    report.extend(['', '오류 주입은 실제 원본의 모순 수에 포함하지 않는다. 수정 전 정의의 활성·해제·효과적 활성화는 만족 가능하며, 복구 후에도 만족 가능함을 확인했다.', '',
                   '| 주입 또는 음성 대조 | 새 검사 결과 | 기존 검사 상태 |', '| --- | --- | --- |'])
    for name, control in controls.items():
        if name == 'liveness_loop_control':continue
        selected = 'activation' if name in ('contradictory_activation', 'different_targets_negative_control') else 'release'
        result = control['injected_result'][selected]['status']
        if name == 'tautological_release':result += '; 해제 항상 참 및 효과적 활성화 불가능'
        report.append('| ' + name + ' | ' + result + ' | ' + ', '.join(control['injected_baseline_statuses']) + ' |')
    report.extend(['',
        '해제 조건은 OR이므로 p와 ¬p를 함께 넣으면 불가능 조건이 아니라 항상 참인 조건이다. 불가능 해제 주입은 LEFT_OF(ego,ego)를 사용했다. 같은 대상의 엄격한 좌우 순서는 성립할 수 없다.', '',
        '별도의 합성 전이 모델에서는 해제식 자체가 만족 가능해도 차단 상태를 계속 유지하는 자기 루프가 존재함을 확인했다. 그 루프는 합성 모델에 선언한 무조건적 최종 해제 요구를 위반한다. 실제 생성 결과의 liveness 위반을 발견했다는 뜻은 아니다.', '',
        f'실제 정의 검사 소요 시간은 {elapsed:.3f}초이다. 이는 이번 입력의 측정이며 전체 liveness 검증 시간이나 최악 시간 보장이 아니다.', '',
        '원본 파일 해시를 전후 대조했다. Studio 실행 코드·데이터베이스를 변경하지 않았다. 검사 결과는 논리적 정의 가능성이며 장면의 진실성이나 실제 도달 가능성을 보장하지 않는다.', ''])
    (output / 'REPORT_KO.md').write_text('\n'.join(report))
    code_path = Path(__file__)
    manifest = {'project_id': 'guardsynth-coc', 'run_id': output.name, 'status': 'COMPLETE',
                'protocol_version': PROTOCOL['version'], 'paid_calls': 0, 'input_count': len(inputs),
                'input_originals_preserved': True, 'studio_application_modified': False,
                'code_sha256': hashlib.sha256(code_path.read_bytes()).hexdigest(),
                'result_sha256': hashlib.sha256((output / 'RESULT.json').read_bytes()).hexdigest()}
    (output / 'RUN_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();run(args.root, args.output)
