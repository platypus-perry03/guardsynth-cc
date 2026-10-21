"""Boundary, radial-distance, sampling and leakage tests for continuation training."""
from pathlib import Path
import sys

EXPERIMENT = Path(__file__).resolve().parents[1] / 'experiments/paper1_external_methods'
sys.path.insert(0, str(EXPERIMENT))
import position_hold_training_profile as profile
import train_position_hold_selection as training
import run_position_hold_selection as diagnostic


def candidate(index, xy):
    points = [[0, 0] for _ in profile.TIMES_MS]
    points[index] = xy
    return dict(label='A', xy_mm=points, progress=10)


def test_inclusive_radius_and_time():
    compiled = profile.compile_contract(profile.contract(2000))
    assert profile.verdict(compiled, candidate(5, [120, 160])) == 'SAT'
    assert profile.verdict(compiled, candidate(5, [201, 0])) == 'UNSAT'
    assert profile.verdict(compiled, candidate(6, [1000, 0])) == 'SAT'


def test_excursion_and_duration():
    short = profile.compile_contract(profile.contract(500))
    long = profile.compile_contract(profile.contract(2000))
    assert profile.verdict(short, candidate(3, [250, 0])) == 'SAT'
    assert profile.verdict(long, candidate(3, [250, 0])) == 'UNSAT'
    # Returning to zero at the endpoint does not erase an earlier excursion.
    assert profile.verdict(long, candidate(1, [0, 250])) == 'UNSAT'
    # A component-wise 0.2m bound would incorrectly admit this candidate.
    assert profile.verdict(long, candidate(2, [150, 150])) == 'UNSAT'


def test_profile_rejects_semantic_drift():
    for field, value in (('radius_mm', 201), ('endpoint_inclusive', False), ('coordinate_unit', 'm')):
        raw = profile.contract(2000)
        raw[field] = value
        try:
            profile.validate(raw)
        except ValueError:
            pass
        else:
            raise AssertionError(field)


def test_group_disjoint_generator_and_rule_information():
    forbidden = {training.geometry_key(x['candidates']) for x in diagnostic.templates()}
    groups = [training.generate_profiles(20, seed, forbidden) for seed in (901, 902, 903)]
    keys = [{training.geometry_key(c) for c in group} for group in groups]
    assert not keys[0] & keys[1] and not keys[0] & keys[2] and not keys[1] & keys[2]
    candidates = sorted(groups[0][0], key=lambda c: c['label'])
    first = dict(candidates=candidates, hold_ms=500, encoding='xy_waypoints')
    second = dict(first, hold_ms=2000)
    assert training.prompt(first, 'p0') == training.prompt(second, 'p0')
    assert training.prompt(first, 'p1') != training.prompt(second, 'p1')
    assert training.prompt(first, 'p2') != training.prompt(second, 'p2')
    assert diagnostic.reference(first) != diagnostic.reference(second)
    assert profile.render(profile.contract(500)) in training.prompt(first, 'p2')


def test_independent_oracle_agrees_with_core():
    groups = training.generate_profiles(8, 992, set())
    for hold in (500, 2000):
        compiled = profile.compile_contract(profile.contract(hold))
        for candidates in groups:
            for c in candidates:
                expected = 'SAT' if diagnostic.maximum_squared_mm(c, hold) <= 40000 else 'UNSAT'
                assert profile.verdict(compiled, c) == expected
