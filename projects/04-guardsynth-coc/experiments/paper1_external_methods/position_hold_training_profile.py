"""Restricted, supplied position-hold EBLC profile for the Project04 experiment.

Coordinates are integer millimetres relative to the initial position. This
profile checks the listed samples, not continuous-time vehicle dynamics.
"""
from pathlib import Path
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'PROJECT_REGISTRY.json').exists())
sys.path[:0] = [str(ROOT), str(ROOT / 'platforms/eblc-bcv/src')]
from cli.solver_runtime import configure_project_z3
configure_project_z3(ROOT)
from guard_synth_eblc.core_ir import parse_core_model
from guard_synth_eblc.smt_compiler import compile_core_model, solve_assignment

TIMES_MS = (0, 250, 500, 1000, 1500, 2000, 2100)
VERSION = 'supplied-position-hold-eblc-profile-v0.1'


def contract(hold_ms):
    if type(hold_ms) is not int or hold_ms not in (500, 2000):
        raise ValueError('unsupported hold duration')
    return dict(version=VERSION, subject='ego', target='initial_xy_position',
                restriction='RADIAL_DISTANCE_AT_MOST', radius_mm=200,
                hold_ms=hold_ms, time_unit='ms', coordinate_unit='mm',
                sample_times_ms=list(TIMES_MS), endpoint_inclusive=True,
                release='MOTION_PERMITTED_AFTER_HOLD',
                assumption='LISTED_WAYPOINTS_RELATIVE_TO_INITIAL_ORIGIN',
                source_kind='SUPPLIED_SYNTHETIC_RULE',
                source_refs=['guardsynth-coc/position-hold-training-001/supplied-rule'])


def validate(raw):
    if raw != contract(raw['hold_ms']):
        raise ValueError('unsupported position-hold profile fields')
    return raw


def render(raw):
    validate(raw)
    hold = raw['hold_ms'] / 1000
    return (f"Hold the ego vehicle's initial position for at least {hold:.1f} s. "
            f"At every listed waypoint with t <= {hold:.1f} s, including the endpoint, "
            "the radial XY distance from the initial position must be at most 0.200 m. "
            "Movement after that period is permitted.")


def literal(value):
    return dict(op='literal', sort='INT', value=value, enum_name=None, unit='1', frame=None)


def variable(name):
    return dict(op='var', name=name, offset=0)


def binary(op, left, right):
    return dict(op=op, left=left, right=right)


def lower(raw):
    validate(raw)
    refs = raw['source_refs']
    declarations = [dict(name=f'{axis}_{i}', sort='INT', time_varying=False,
                         enum_name=None, enum_values=[], unit='1', frame=None, source_refs=refs)
                    for i in range(len(TIMES_MS)) for axis in ('x', 'y')]
    clauses = []
    for i, t in enumerate(TIMES_MS):
        if t > raw['hold_ms']:
            continue
        x, y = variable(f'x_{i}'), variable(f'y_{i}')
        squared = binary('add', binary('mul', x, x), binary('mul', y, y))
        clauses.append(dict(id=f'hold_sample_{i}', kind='INVARIANT', enforcement='INITIAL',
                            formula=binary('le', squared, literal(raw['radius_mm'] ** 2)),
                            source_refs=refs, description=f'Inclusive radial bound at {t}ms.'))
    return dict(grammar_version='eblc-core-v0.1', model_id=f'position_hold_{raw["hold_ms"]}',
                horizon=2, source_refs=refs, claim_scope='SYNTHETIC_LISTED_WAYPOINTS_ONLY',
                declarations=declarations, clauses=clauses,
                queries=[dict(id='consistency', formula=dict(op='literal', sort='BOOL', value=True,
                              enum_name=None, unit=None, frame=None), expected='SAT',
                              classification='CONSISTENCY', source_refs=refs,
                              description='A zero-distance assignment is feasible.')])


def compile_contract(raw):
    return compile_core_model(parse_core_model(lower(raw)))


def verdict(compiled, candidate):
    if len(candidate['xy_mm']) != len(TIMES_MS) or candidate['xy_mm'][0] != [0, 0]:
        raise ValueError('expected listed waypoints relative to initial origin')
    values = {(f'{axis}_{i}', None): value
              for i, xy in enumerate(candidate['xy_mm']) for axis, value in zip(('x', 'y'), xy)}
    if any(type(value) is not int for value in values.values()):
        raise ValueError('coordinates must be integer millimetres')
    return solve_assignment(compiled, values)['status']
