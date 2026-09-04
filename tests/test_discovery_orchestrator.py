import unittest

from discovery import DiscoveryEngine
from discovery.models import Experiment, Hypothesis
from discovery.orchestrator import DiscoveryOrchestrator
from jarvis.dispatcher import DispatchResult


class FakeDispatcher:
    def __init__(self, result):
        self.result = result
        self.tasks = []

    def dispatch(self, task, *, security=None):
        self.tasks.append((task, security))
        return self.result


class DiscoveryOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.discovery = DiscoveryEngine()
        self.hypothesis = self.discovery.register_hypothesis(
            Hypothesis(
                hypothesis_id="h1",
                statement="A changes B",
                null_hypothesis="A does not change B",
                falsification_criteria=("effect <= 0",),
            )
        )
        self.experiment = self.discovery.design_experiment(
            Experiment(
                experiment_id="e1",
                hypothesis_id=self.hypothesis.hypothesis_id,
                objective="Measure B",
                procedure=("run controlled trial",),
                controls=("baseline",),
                metrics=("effect",),
                required_evidence=("measurement",),
                independent_group="lab-a",
            )
        )

    def test_experiment_is_dispatched_as_governed_task_and_recorded(self):
        dispatcher = FakeDispatcher(
            DispatchResult(
                "experiment:e1",
                "passed",
                result={
                    "success": True,
                    "observations": {"effect": 1.5},
                    "conclusion": "effect observed",
                    "evidence": [
                        {
                            "evidence_id": "ev1",
                            "source": "lab-a",
                            "claim": "effect measured",
                            "independent_group": "lab-a",
                        }
                    ],
                },
            )
        )
        bridge = DiscoveryOrchestrator(self.discovery, dispatcher)

        outcome = bridge.execute_experiment(self.experiment, execution_capability="research.execute")

        self.assertEqual(outcome.dispatch.status, "passed")
        self.assertIsNotNone(outcome.result)
        self.assertEqual(dispatcher.tasks[0][0]["capability"], "research.execute")
        self.assertEqual(dispatcher.tasks[0][0]["input"]["hypothesis_id"], "h1")
        self.assertEqual(self.discovery.results["e1"][0].observations["effect"], 1.5)

    def test_failed_dispatch_does_not_create_scientific_result(self):
        dispatcher = FakeDispatcher(DispatchResult("experiment:e1", "rejected", error="denied"))
        bridge = DiscoveryOrchestrator(self.discovery, dispatcher)

        outcome = bridge.execute_experiment(self.experiment, execution_capability="research.execute")

        self.assertIsNone(outcome.result)
        self.assertNotIn("e1", self.discovery.results)

    def test_execution_payload_must_contain_structured_evidence_list(self):
        dispatcher = FakeDispatcher(
            DispatchResult("experiment:e1", "passed", result={"success": True, "observations": {}, "evidence": {}})
        )
        bridge = DiscoveryOrchestrator(self.discovery, dispatcher)

        with self.assertRaises(ValueError):
            bridge.execute_experiment(self.experiment, execution_capability="research.execute")


if __name__ == "__main__":
    unittest.main()
