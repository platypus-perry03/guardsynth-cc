"""guardsynth-coc: offline feasibility probe for Studio properties 1–4.

This experiment neither edits candidates nor installs checks in the Studio.
Conditional ALLOW definitions are not assertions that the observed action was
justified. Textual CoC justification needs explicit claim bindings, so this
probe reports that gap separately rather than inventing bindings from text.
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

from guard_synth.studio_grounded_sequence import _supported_atom, _supports_evidence, _uncertain_entities
from guard_synth.studio_sequence import compile_sequence, verify_compiled


PROTOCOL = {
    'project_id': 'guardsynth-coc', 'version': 'studio-property-probe-v0.2',
    'scope': 'Immediately prior/current pair; existing model drafts only.',
    'p1': 'Explicit claim bindings only for CoC. Separately test current support for conditional ALLOW guards; do not treat an inactive candidate as a false CoC claim.',
    'p2': 'Experiment checklist: ENTER/START permission must bind PATH_CLEAR to its target; a green-signal premise must bind signal applicability to ego/target. This is a review criterion, not universal traffic law.',
    'p3': 'Aggregate permissions with same-subject/action/target/movement prohibitions. A potential overlap is a diagnostic countermodel, not a model error or actual violation.',
    'p4': 'Compare linked nearest-past CAN measurements with HOLD/CONTINUE. Gray speeds and stale/missing/unlinked CAN remain unconfirmed; do not use CAN to prove ENTER.',
    'normalization': 'Old PATH_CLEAR(ego, zone/lane) is evaluated as PATH_CLEAR(zone/lane, null) in a separate experimental copy. PATH_CLEAR(ego, null) remains unbound. Original files and baseline semantics stay unchanged.',
    'can_max_age_us': 600000, 'stationary_max_kmh': 0.5, 'moving_min_kmh': 2.0,
    'solver_timeout_ms': 500, 'scene_truth_certified': False,
}


def canonical(atom, kinds):
    key = (atom['predicate'], atom['subject_ref'], atom['object_ref'])
    if key[0] == 'PATH_CLEAR' and key[1] == 'ego' and kinds.get(key[2]) in ('LANE', 'ZONE'):
        return ('PATH_CLEAR', key[2], None)
    return key if _supported_atom(key, kinds) else None


class EvidenceModel:
    """Finite experiment-local Boolean queries with explicit unknown evidence."""
    def __init__(self, records=()):
        self.solver = z3.Solver()
        self.solver.set(timeout=PROTOCOL['solver_timeout_ms'])
        self.variables = {}
        for key, truth in records:
            atom = self.atom(key)
            if truth in ('TRUE', 'FALSE'):
                self.solver.add(atom == (truth == 'TRUE'))
            elif truth == 'CONFLICT':
                self.solver.add(z3.BoolVal(False))

    def atom(self, key):
        key = tuple(key)
        if key not in self.variables:
            self.variables[key] = z3.Bool('p_' + hashlib.sha256(repr(key).encode()).hexdigest()[:20])
        return self.variables[key]

    def query(self, expression):
        self.solver.push()
        self.solver.add(expression)
        checked = self.solver.check()
        witness = {str(key): str(self.solver.model().eval(value, model_completion=True)) for key, value in self.variables.items()} if checked == z3.sat else {}
        reason = self.solver.reason_unknown() if checked == z3.unknown else None
        self.solver.pop()
        return {'status': str(checked).upper(), 'witness': witness, 'reason_unknown': reason}

    def support(self, expression):
        base = self.query(z3.BoolVal(True))
        if base['status'] != 'SAT':
            return {'status': 'INPUT_CONFLICT' if base['status'] == 'UNSAT' else 'SOLVER_UNKNOWN', 'base': base}
        negative = self.query(z3.Not(expression))
        positive = self.query(expression)
        status = 'SUPPORTED' if negative['status'] == 'UNSAT' else 'CONTRADICTED' if positive['status'] == 'UNSAT' else 'UNCONFIRMED' if negative['status'] == positive['status'] == 'SAT' else 'SOLVER_UNKNOWN'
        return {'status': status, 'negative': negative, 'positive': positive}


def guard_expression(model, guards, kinds):
    terms = []
    invalid = []
    for i, guard in enumerate(guards):
        key = canonical(guard['atom'], kinds)
        if key is None:
            invalid.append(i)
            # The unsupported condition is unknown, never silently true.
            key = ('UNBOUND', json.dumps(guard['atom'], sort_keys=True), None)
        atom = model.atom(key)
        terms.append(atom if guard['expected_truth'] == 'TRUE' else z3.Not(atom))
    return z3.And(*terms), invalid


def justification_support(model, bindings, kinds):
    if not bindings:
        return {'status': 'CLAIM_BINDING_UNAVAILABLE'}
    formula, invalid = guard_expression(model, bindings, kinds)
    result = model.support(formula)
    return {**result, 'invalid_guard_indexes': invalid}


def required_conditions(definition, action, kinds):
    guards = definition['activation_all_of'] + definition['preconditions']
    keys = {canonical(g['atom'], kinds) for g in guards if g['expected_truth'] == 'TRUE'}
    missing = []
    target = definition['action_target_ref']
    if action in ('ENTER', 'START'):
        if kinds.get(target) not in ('LANE', 'ZONE'):
            missing.append({'predicate': 'BOUND_ACTION_TARGET', 'target': target})
        elif ('PATH_CLEAR', target, None) not in keys:
            missing.append({'predicate': 'PATH_CLEAR', 'target': target})
        for key in keys:
            if key and key[0] == 'SIGNAL_GREEN' and not any(('APPLIES_TO', key[1], obj) in keys for obj in ('ego', target)):
                missing.append({'predicate': 'APPLIES_TO', 'signal': key[1], 'target': target})
    return {'status': 'CHECKLIST_OMISSION' if missing else 'CHECKLIST_PRESENT', 'missing': missing}


def permission_support(model, definition, action, definitions, states, kinds):
    allowed, invalid = guard_expression(model, definition['activation_all_of'] + definition['preconditions'], kinds)
    key = (definition['subject_ref'], action, definition['action_target_ref'], definition['movement_ref'])
    blockers = []
    ids = []
    for other in definitions:
        if other['effect'] != 'FORBID' or action not in other['actions']:
            continue
        if (other['subject_ref'], action, other['action_target_ref'], other['movement_ref']) != key:
            continue
        cid = other['condition_id']
        state = states[cid]
        if state['active_obligation']:
            term = z3.BoolVal(True)
        elif state['state'] in ('RELEASED', 'INACTIVE'):
            term = z3.BoolVal(False)
        else:
            term = model.atom(('ACTIVE', cid, None))
        blockers.append(term)
        ids.append(cid)
    forbidden = z3.Or(*blockers)
    support = model.support(z3.And(allowed, z3.Not(forbidden)))
    overlap = model.query(z3.And(allowed, forbidden))
    result_status = support['status']
    if result_status == 'CONTRADICTED':
        result_status = 'PERMISSION_BLOCKED' if model.support(forbidden)['status'] == 'SUPPORTED' else 'CONDITION_NOT_MET'
    return {'status': result_status, 'support': support, 'overlap': overlap,
            'blocker_condition_ids': ids, 'invalid_guard_indexes': invalid,
            'claim': 'Aggregate permission assessment, not a claim that the CoC asserted permission.'}


def can_action_support(action, request):
    code = action['code']
    if code not in ('HOLD', 'CONTINUE'):
        return {'status': 'TRANSITION_BINDING_UNAVAILABLE' if code in ('START', 'STOP') else 'NOT_APPLICABLE'}
    current = request['frames'][-1]['timestamp_us']
    records = (request.get('vehicle_state') or {}).get('frames', [])
    aligned = [r for r in records if r['frame_timestamp_us'] == current]
    if not aligned or not aligned[-1].get('sample'):
        return {'status': 'CAN_UNAVAILABLE'}
    row = aligned[-1];sample = row['sample'];age = current - sample['timestamp_us']
    if age < 0 or age > PROTOCOL['can_max_age_us'] or age != row['age_us']:
        return {'status': 'CAN_ALIGNMENT_UNCONFIRMED', 'age_us': age}
    if 'CAN:' + str(sample['timestamp_us']) not in action['evidence_refs']:
        return {'status': 'CAN_LINK_UNAVAILABLE'}
    speed = sample.get('vehicle_speed_kmh')
    if not isinstance(speed, (int, float)) or speed < 0:
        return {'status': 'CAN_VALUE_UNCONFIRMED'}
    if PROTOCOL['stationary_max_kmh'] < speed < PROTOCOL['moving_min_kmh']:
        return {'status': 'MOTION_GRAY_ZONE', 'speed_kmh': speed, 'age_us': age}
    solver = z3.Solver();solver.set(timeout=PROTOCOL['solver_timeout_ms'])
    measured = z3.Real('measured_speed_kmh')
    solver.add(measured == z3.RealVal(str(speed)))
    solver.add(measured <= PROTOCOL['stationary_max_kmh'] if code == 'HOLD' else measured >= PROTOCOL['moving_min_kmh'])
    checked = solver.check()
    return {'status': 'CAN_RECORD_CONSISTENT' if checked == z3.sat else 'CAN_RECORD_CONTRADICTION' if checked == z3.unsat else 'SOLVER_UNKNOWN',
            'speed_kmh': speed, 'age_us': age, 'sample': sample,
            'claim': 'Consistency with the supplied nearest-past measurement; not certification of image-time vehicle state.'}


def evidence_model(coc, constraints, previous_entities, current_evidence):
    kinds = {e['entity_id']: e['kind'] for e in previous_entities + coc['entities']}
    uncertain = _uncertain_entities(coc['entities'], previous_entities)
    records = []
    for value in coc['relations'] + constraints['facts']:
        atom = value.get('atom', value);key = canonical(atom, kinds)
        if key is None:
            continue
        # Evidence kind follows the original predicate, not a normalized alias.
        original_key = (atom['predicate'], atom['subject_ref'], atom['object_ref'])
        valid = _supports_evidence(original_key, value['evidence_refs'], current_evidence)
        valid = valid and (bool(value.get('evidence_note', '').strip()) if 'atom' in value else True)
        valid = valid and key[1] not in uncertain and key[2] not in uncertain
        records.append((key, value['truth'] if valid else 'UNKNOWN'))
    return EvidenceModel(records), kinds


def mutation_controls(source):
    """In-memory perturbations; never include these in model-error counts."""
    def payloads(name, point):
        directory = source / name
        values = [json.loads((directory / f'revision_{point}_{suffix}.json').read_text()) for suffix in ('coc_candidate', 'constraints_candidate', 'coc_request')]
        return values[0], values[1], values[2]['input_data']
    coc, con, req = payloads('scene-1100-pair-002', 1)
    model, kinds = evidence_model(coc, con, [], [req['frames'][-1]['frame_id']])
    visibility = next(f['atom'] for f in con['facts'] if f['atom']['predicate'] == 'VISIBILITY_INSUFFICIENT' and f['truth'] == 'TRUE')
    wrong = [{'atom': visibility, 'expected_truth': 'FALSE'}]
    corrected = [{'atom': visibility, 'expected_truth': 'TRUE'}]
    controls = {'P1': {'source': 'scene-1100-pair-002 point 1', 'kind': 'SYNTHETIC_EXPLICIT_CLAIM_BINDING',
                       'injected_claim': wrong, 'injected_result': justification_support(model, wrong, kinds),
                       'corrected_result': justification_support(model, corrected, kinds)}}
    allowed = next(d for d in con['new_definitions'] if d['effect'] == 'ALLOW')
    controls['P2'] = {'source': 'scene-1100-pair-002 point 1', 'kind': 'SYNTHETIC_GUARD_REMOVAL',
                      'original_result': required_conditions(allowed, 'ENTER', kinds)}
    removed = deepcopy(allowed)
    removed['preconditions'] = [g for g in removed['preconditions'] if g['atom']['predicate'] != 'PATH_CLEAR']
    controls['P2']['injected_result'] = required_conditions(removed, 'ENTER', kinds)
    controls['P2']['restored_result'] = required_conditions(allowed, 'ENTER', kinds)
    # Suppose the currently unknown ALLOW prerequisites were later confirmed.
    # Keep the generated visibility prohibition active; candidate support alone
    # still cannot establish the aggregate permission.
    allowed_formula, invalid = guard_expression(model, allowed['activation_all_of'] + allowed['preconditions'], kinds)
    assert not invalid
    model.solver.add(allowed_formula)
    states = {d['condition_id']: {'state': 'ACTIVE', 'active_obligation': True} for d in con['new_definitions'] if d['effect'] == 'FORBID'}
    controls['P3'] = {'source': 'scene-1100-pair-002 point 1', 'kind': 'HYPOTHETICAL_ALLOW_PREREQUISITES_CONFIRMED',
                      'individual_allow_support': model.support(allowed_formula),
                      'aggregate_permission': permission_support(model, allowed, 'ENTER', con['new_definitions'], states, kinds)}
    moments = []
    for point in (1, 2):
        coc, con, req = payloads('scene-0061-pair-005', point)
        current = req['frames'][-1];evidence = [f['frame_id'] for f in req['frames']];now = [current['frame_id']]
        for r in req['vehicle_state']['frames']:
            if r.get('sample'):
                ref = 'CAN:' + str(r['sample']['timestamp_us']);evidence.append(ref)
                if r['frame_timestamp_us'] == current['timestamp_us']:
                    now.append(ref)
        moments.append({'id': f'control-{point}', 'ordinal': point-1, 't0_us': current['timestamp_us'],
                        'frame_ids': evidence, 'current_evidence_refs': now, 'reviewed': True, 'coc': coc, 'constraints': con})
    original = deepcopy(moments)
    before = verify_compiled(compile_sequence(moments, {'sources': []}))['scenes'][-1]
    injected = deepcopy(moments)
    injected[-1]['coc']['observed_actions'][0]['code'] = 'HOLD'
    old_check = verify_compiled(compile_sequence(injected, {'sources': []}))['scenes'][-1]
    new_check = can_action_support(injected[-1]['coc']['observed_actions'][0], req)
    restored = can_action_support(moments[-1]['coc']['observed_actions'][0], req)
    assert moments == original
    controls['P4'] = {'source': 'scene-0061-pair-005 point 2', 'kind': 'SYNTHETIC_ACTION_LABEL_FLIP',
                      'original_baseline': before['status'], 'injected_action': 'HOLD',
                      'injected_baseline': old_check['status'], 'injected_baseline_codes': old_check['codes'],
                      'injected_result': new_check, 'restored_result': restored}
    assert controls['P1']['injected_result']['status'] == 'CONTRADICTED'
    assert controls['P1']['corrected_result']['status'] == 'SUPPORTED'
    assert controls['P2']['injected_result']['status'] == 'CHECKLIST_OMISSION'
    assert controls['P2']['restored_result']['status'] == 'CHECKLIST_PRESENT'
    assert controls['P3']['individual_allow_support']['status'] == 'SUPPORTED'
    assert controls['P3']['aggregate_permission']['status'] == 'PERMISSION_BLOCKED'
    assert before['status'] == old_check['status'] == 'PASS'
    assert new_check['status'] == 'CAN_RECORD_CONTRADICTION'
    assert restored['status'] == 'CAN_RECORD_CONSISTENT'
    return controls


def run(source, baseline, output):
    output.mkdir(parents=True, exist_ok=False)
    (output / 'protocol.json').write_text(json.dumps(PROTOCOL, ensure_ascii=False, indent=2) + '\n')
    inputs = {};rows = [];points = [];timings = [];baseline_times = [];probe_times = [];actual_actions = Counter()
    for directory in sorted(source.glob('scene-*-pair-*')):
        path = baseline / (directory.name.replace('-', '_') + '.json')
        raw = path.read_bytes();inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        replay = json.loads(raw);start = time.perf_counter()
        verified = verify_compiled(replay['compiled'])
        baseline_times.append(time.perf_counter() - start)
        probe_start = time.perf_counter()
        previous_entities = []
        for point in (1, 2):
            payloads = []
            for suffix in ('coc_candidate', 'constraints_candidate', 'coc_request'):
                p = directory / f'revision_{point}_{suffix}.json'
                raw = p.read_bytes();inputs[str(p)] = hashlib.sha256(raw).hexdigest();payloads.append(json.loads(raw))
            coc, constraints, request = payloads;request = request['input_data']
            current = request['frames'][-1];current_evidence = [current['frame_id']]
            for r in (request.get('vehicle_state') or {}).get('frames', []):
                if r['frame_timestamp_us'] == current['timestamp_us'] and r.get('sample'):
                    current_evidence.append('CAN:' + str(r['sample']['timestamp_us']))
            stored = replay['compiled']['scenes'][point-1];base = verified['scenes'][point-1]
            model, kinds = evidence_model(coc, constraints, previous_entities, current_evidence)
            prefix = {'pair': directory.name, 'point': point, 'baseline_status': base['status'], 'baseline_codes': base['codes'], 'explanation': coc['explanation']}
            def record(prop, unit, result, **context):
                rows.append({**prefix, 'property': prop, 'unit': unit, **deepcopy(result), **context})
            record('P1', 'CoC justification binding', justification_support(model, [], kinds), note='Existing schema has explanation text but no reason-to-action claim bindings. No automatic textual justification verdict is issued.')
            definitions = stored['constraints']
            for d in definitions:
                if d['effect'] != 'ALLOW':
                    continue
                guards = d['activation_all_of'] + d['preconditions']
                # Empty reasons do not become a vacuous proof of justification.
                record('P1', 'Conditional ALLOW support', justification_support(model, guards, kinds), condition_id=d['condition_id'], guards=guards, note='Auxiliary support assessment; inactive/unconfirmed candidate is not a CoC contradiction.')
                for action in d['actions']:
                    record('P3', 'Aggregate permission', permission_support(model, d, action, definitions, stored['states'], kinds), condition_id=d['condition_id'], action=action, target=d['action_target_ref'])
            for d in constraints['new_definitions']:
                if d['effect'] == 'ALLOW':
                    for action in d['actions']:
                        if action in ('START', 'ENTER'):
                            record('P2', 'New permission definition', required_conditions(d, action, kinds), condition_id=d['condition_id'], action=action, target=d['action_target_ref'])
            for action in coc['observed_actions']:
                actual_actions[action['code']] += 1
                if action['code'] in ('START', 'ENTER'):
                    matching = [d for d in definitions if d['effect'] == 'ALLOW' and action['code'] in d['actions'] and all(d[k] == action[k] for k in ('subject_ref', 'action_target_ref', 'movement_ref'))]
                    result = {'status': 'ACTION_JUSTIFICATION_COVERAGE_MISSING', 'missing': [{'predicate': 'ALLOW_WITH_TARGET_PRECONDITIONS', 'target': action['action_target_ref']}]} if not matching else {'status': 'CHECKLIST_PRESENT' if any(required_conditions(d, action['code'], kinds)['status'] == 'CHECKLIST_PRESENT' for d in matching) else 'CHECKLIST_OMISSION'}
                    record('P2', 'Observed action justification coverage', result, action=action['code'], target=action['action_target_ref'], note='Coverage requirement for a reviewed justification; observed ENTER itself remains an observation, not a permission claim.')
                record('P4', 'CAN/action consistency', can_action_support(action, request), action=action['code'], target=action['action_target_ref'])
            point_rows = [r for r in rows if r['pair'] == directory.name and r['point'] == point]
            points.append({**prefix, 'new_hard_contradictions': sum(r['status'] in ('CAN_RECORD_CONTRADICTION',) for r in point_rows),
                           'checklist_omissions': sum(r['status'] in ('CHECKLIST_OMISSION', 'ACTION_JUSTIFICATION_COVERAGE_MISSING') for r in point_rows),
                           'coc_claim_binding_available': False})
            previous_entities = coc['entities']
        probe_times.append(time.perf_counter() - probe_start)
        timings.append(time.perf_counter() - start)
    assert len(points) == 100 and len(timings) == 50
    controls = mutation_controls(source)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == sha for p, sha in inputs.items())
    summaries = {prop: dict(Counter(r['status'] for r in rows if r['property'] == prop)) for prop in ('P1', 'P2', 'P3', 'P4')}
    baseline_counts = dict(Counter(p['baseline_status'] for p in points))
    summary = {'project_id': 'guardsynth-coc', 'status': 'COMPLETE', 'paid_calls': 0,
               'pairs': len(timings), 'points': len(points), 'actual_actions': dict(actual_actions),
               'baseline_status_counts': baseline_counts, 'property_status_counts': summaries,
               'new_hard_contradiction_points': sum(p['new_hard_contradictions'] > 0 for p in points),
               'previously_passed_points_with_new_omissions': sum(p['baseline_status'] == 'PASS' and p['checklist_omissions'] > 0 for p in points),
               'total_baseline_verify_and_probe_s': sum(timings), 'max_pair_s': max(timings),
               'baseline_verify_s': sum(baseline_times), 'added_probe_s': sum(probe_times),
               'max_added_probe_pair_s': max(probe_times),
               'input_originals_preserved': True, 'studio_modified': False,
               'mutation_controls': {'passed': 4, 'counted_as_real_model_errors': False},
               'limitations': ['Older prompt outputs; not fresh current-prompt outputs.', 'No independent human gold labels, precision/recall or safety certification.', 'START/STOP are absent; observed ENTER appears once.', 'P1 textual CoC inference unavailable without explicit bindings.', 'P3 diagnostic overlaps are not false conditional rules.'],
               'points_detail': points}
    (output / 'checks.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (output / 'mutation_controls.json').write_text(json.dumps(controls, ensure_ascii=False, indent=2) + '\n')
    (output / 'RESULT.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (output / 'input_hashes.json').write_text(json.dumps(inputs, indent=2) + '\n')
    columns = ['pair', 'point', 'property', 'unit', 'status', 'baseline_status', 'baseline_codes', 'condition_id', 'action', 'target', 'missing', 'speed_kmh', 'age_us', 'blocker_condition_ids', 'explanation', 'note']
    with (output / 'property_comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, columns);writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k], ensure_ascii=False) if isinstance(row.get(k), (dict, list)) else row.get(k, '') for k in columns})
    print(json.dumps({k: v for k, v in summary.items() if k != 'points_detail'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    run(args.source, args.baseline, args.output)
