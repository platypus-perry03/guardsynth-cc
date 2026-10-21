"""Boundary and history cases for the position-hold selection oracle."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments/paper1_external_methods'))
from run_position_hold_selection import maximum_squared_mm, score, reference


def candidate(points):
    return dict(label='A',xy_mm=points,progress=10)


def test_exact_xy_radius_and_diagonal_excess():
    points=[[0,0],[120,160],[0,0],[0,0],[0,0],[0,0],[900,0]]
    assert maximum_squared_mm(candidate(points),500)==200**2
    points[1]=[160,160]
    assert maximum_squared_mm(candidate(points),500)>200**2


def test_mid_interval_excursion_is_not_erased_by_return():
    points=[[0,0],[201,0],[0,0],[0,0],[0,0],[0,0],[900,0]]
    assert maximum_squared_mm(candidate(points),500)==201**2


def test_hold_endpoint_is_included_and_later_motion_permitted():
    points=[[0,0],[0,0],[200,0],[0,0],[0,0],[200,0],[900,0]]
    assert maximum_squared_mm(candidate(points),500)==200**2
    assert maximum_squared_mm(candidate(points),2000)==200**2
    points[2]=[201,0]
    assert maximum_squared_mm(candidate(points),500)>200**2


def test_measurement_tolerance_is_separate_from_primary_rule():
    moving=candidate([[0,0],[0,0],[210,0],[0,0],[0,0],[0,0],[0,0]])
    still=dict(label='B',xy_mm=[[0,0]]*7,progress=0)
    case=dict(hold_ms=500,candidates=[moving,still])
    verdict=score(case,'A')
    assert verdict['violation'] and not verdict['tolerance_violation']
    assert reference(case)=='B'
    assert score(case,'INVALID')['violation'] is None


def test_distance_is_relative_to_initial_position():
    points=[[1000,2000],[1120,2160],[1000,2000],[1000,2000],[1000,2000],[1000,2000],[1000,2000]]
    assert maximum_squared_mm(candidate(points),500)==200**2
