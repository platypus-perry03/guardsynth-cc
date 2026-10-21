"""Analytic examples and label invariance for nominal panel agreement."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "experiments/kiee_review_revision/analyze_reviewer_agreement.py"
spec = importlib.util.spec_from_file_location("reviewer_agreement", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AgreementTests(unittest.TestCase):
    def test_skewed_panel_has_distinct_chance_models(self):
        result = module.coefficients([["Y"] * 4, ["Y", "Y", "Y", "N"]], ["Y", "N"])
        self.assertAlmostEqual(result["raw_agreement"], 0.75)
        self.assertAlmostEqual(result["fleiss_kappa"], -1 / 7)
        self.assertAlmostEqual(result["gwet_ac1"], 17 / 25)

    def test_unanimous_single_used_category(self):
        result = module.coefficients([["Y"] * 4] * 3, ["Y", "N"])
        self.assertIsNone(result["fleiss_kappa"])
        self.assertEqual(result["gwet_ac1"], 1)

    def test_permutation_and_exact_cross_check(self):
        votes = [["A", "A", "B", "C"], ["B", "B", "B", "A"], ["C"] * 4]
        expected = module.pairwise_exact_check(votes, ["A", "B", "C"])
        actual = module.coefficients([list(reversed(row)) for row in reversed(votes)], ["C", "B", "A"])
        for key, value in expected.items():
            self.assertAlmostEqual(actual[key], value)

    def test_incomplete_panel_is_rejected(self):
        with self.assertRaises(ValueError):
            module.coefficients([["Y", "N"], ["Y"]], ["Y", "N"])


if __name__ == "__main__":
    unittest.main()
