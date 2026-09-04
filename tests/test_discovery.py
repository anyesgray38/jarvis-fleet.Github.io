import unittest

from discovery import DiscoveryEngine, Evidence, Experiment, ExperimentResult, Hypothesis
from discovery.models import KnowledgeState
from discovery.promotion import readiness
from discovery.stats import permutation_p_value


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.engine = DiscoveryEngine()
        self.engine.register_hypothesis(Hypothesis(
            "h1", "representation improves estimator", "no improvement",
            variables=("representation", "error"),
            falsification_criteria=("effect is absent in controlled trials",),
        ))
        self.engine.design_experiment(Experiment(
            "e1", "h1", "compare baseline and treatment",
            ("freeze data", "run baseline", "run treatment"),
            controls=("seed control",), metrics=("error",),
        ))

    def test_requires_falsification_criteria(self):
        with self.assertRaises(ValueError):
            self.engine.register_hypothesis(Hypothesis("bad", "x", "y"))

    def test_records_independent_results(self):
        self.engine.record_result(ExperimentResult(
            "e1", True, {"error": 0.2},
            (Evidence("ev1", "lab-a", "h1", independent_group="lab-a", data={"value": "support"}),),
            reproducible=True,
        ))
        self.engine.record_result(ExperimentResult(
            "e1", True, {"error": 0.18},
            (Evidence("ev2", "lab-b", "h1", independent_group="lab-b", data={"value": "support"}),),
            verified=True,
        ))
        candidate = self.engine.assess_claim("h1")
        self.assertEqual(candidate.state, KnowledgeState.VERIFIED)
        self.assertEqual(len(candidate.independent_groups), 2)

    def test_contradiction_blocks_promotion(self):
        for idx, group, value in (("a", "lab-a", "support"), ("b", "lab-b", "reject")):
            self.engine.record_result(ExperimentResult(
                "e1", True, {"error": 0.2},
                (Evidence("ev" + idx, group, "h1", independent_group=group, data={"value": value}),),
                verified=True,
            ))
        candidate = self.engine.assess_claim("h1")
        self.assertEqual(candidate.state, KnowledgeState.CONFLICTED)
        ok, reasons = readiness(candidate)
        self.assertFalse(ok)
        self.assertIn("conflicting_evidence", reasons)

    def test_permutation_is_deterministic(self):
        p1 = permutation_p_value([1, 2, 3], [4, 5, 6], permutations=100, seed=7)
        p2 = permutation_p_value([1, 2, 3], [4, 5, 6], permutations=100, seed=7)
        self.assertEqual(p1, p2)


if __name__ == "__main__":
    unittest.main()
