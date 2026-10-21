"""guardsynth-coc: definition feasibility semantics and negative controls."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from studio_condition_feasibility_probe import check_definition, guard


KINDS = {'ego': 'EGO', 'zone': 'ZONE', 'other': 'ZONE', 'car': 'VEHICLE'}


def definition(on=None, off=None, pre=None):
    return {'effect': 'ALLOW', 'activation_all_of': on if on is not None else [guard('PATH_CLEAR', 'zone')],
            'release_any_of': off if off is not None else [guard('PATH_CLEAR', 'zone', truth='FALSE')],
            'preconditions': pre or []}


class ConditionFeasibilityTest(unittest.TestCase):
    def test_opposite_activation_is_impossible(self):
        d = definition(on=[guard('PATH_CLEAR', 'zone'), guard('PATH_CLEAR', 'zone', truth='FALSE')])
        r = check_definition(d, KINDS)['activation']
        self.assertEqual(r['status'], 'UNSAT');self.assertEqual(len(r['conflicting_guards']), 2)

    def test_release_is_or_not_and(self):
        d = definition(off=[guard('PATH_CLEAR', 'zone'), guard('PATH_CLEAR', 'zone', truth='FALSE')])
        r = check_definition(d, KINDS)
        self.assertEqual(r['release']['status'], 'SAT')
        self.assertEqual(r['release_tautology']['status'], 'UNSAT')
        self.assertEqual(r['effective_activation']['status'], 'UNSAT')

    def test_irreflexive_release_needs_domain_semantics(self):
        d = definition(off=[guard('LEFT_OF', 'ego', 'ego')])
        self.assertEqual(check_definition(d)['release']['status'], 'SAT')
        self.assertEqual(check_definition(d, KINDS)['release']['status'], 'UNSAT')

    def test_different_targets_and_preconditions_remain_possible(self):
        d = definition(on=[guard('PATH_CLEAR', 'zone'), guard('PATH_CLEAR', 'other', truth='FALSE')])
        self.assertEqual(check_definition(d, KINDS)['activation']['status'], 'SAT')
        d = definition(pre=[guard('PATH_CLEAR', 'zone', truth='FALSE')])
        r = check_definition(d, KINDS)
        self.assertEqual(r['activation']['status'], 'SAT')
        self.assertEqual(r['activation_preconditions']['status'], 'UNSAT')

    def test_inverse_direction_and_cycles_are_impossible(self):
        for guards in ([guard('LEFT_OF', 'ego', 'car'), guard('RIGHT_OF', 'ego', 'car')],
                       [guard('LEFT_OF', 'ego', 'car'), guard('LEFT_OF', 'car', 'zone'), guard('LEFT_OF', 'zone', 'ego')]):
            self.assertEqual(check_definition(definition(on=guards), KINDS)['activation']['status'], 'UNSAT')

    def test_invalid_kind_is_unassessed_not_impossible(self):
        d = definition(on=[guard('PATH_CLEAR', 'ego')])
        self.assertEqual(check_definition(d, KINDS)['activation']['status'], 'NOT_CHECKED_INVALID_GUARDS')

    def test_legacy_target_normalization_preserves_shared_atom(self):
        d = definition(on=[guard('PATH_CLEAR', 'ego', 'zone'), guard('PATH_CLEAR', 'zone', truth='FALSE')])
        self.assertEqual(check_definition(d)['activation']['status'], 'SAT')
        r = check_definition(d, KINDS)['activation']
        self.assertEqual(r['status'], 'UNSAT');self.assertEqual(len(r['normalizations']), 1)

    def test_empty_guards_are_missing_not_vacuous_success(self):
        self.assertEqual(check_definition(definition(on=[]), KINDS)['activation']['status'], 'MISSING_GUARD')
        self.assertEqual(check_definition(definition(off=[]), KINDS)['release']['status'], 'MISSING_GUARD')

    def test_normal_definition_has_possible_activation_and_release(self):
        r = check_definition(definition(), KINDS)
        for name in ('activation', 'release', 'effective_activation'):
            self.assertEqual(r[name]['status'], 'SAT')
        self.assertEqual(r['activation_release_overlap']['status'], 'UNSAT')


if __name__ == '__main__':
    unittest.main()
