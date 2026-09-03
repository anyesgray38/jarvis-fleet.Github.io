import unittest

from jarvis.workflow import WorkflowPlan, WorkflowRunner


class WorkflowTests(unittest.TestCase):
    def test_dependency_order_and_output_reference(self):
        calls = []

        def dispatch(task):
            calls.append(task["task_id"])
            if task["capability"] == "test.first":
                return {"status": "passed", "result": {"value": "ready"}}
            return {"status": "passed", "result": {"ok": task["input"]["value"] == "ready"}}

        plan = WorkflowPlan.from_dict({
            "workflow_id": "wf-1",
            "objective": "run pipeline",
            "steps": [
                {"id": "second", "capability": "test.second", "depends_on": ["first"], "input": {"value": "${first.value}"}},
                {"id": "first", "capability": "test.first"},
            ],
        })
        result = WorkflowRunner(dispatch).run(plan)
        self.assertEqual(result.status, "passed")
        self.assertEqual(calls, ["wf-1:first", "wf-1:second"])
        self.assertEqual(result.steps["second"].result["ok"], True)

    def test_retry_and_escalation(self):
        attempts = []

        def dispatch(task):
            attempts.append(task["task_id"])
            return {"status": "failed", "error": "nope"}

        plan = WorkflowPlan.from_dict({
            "workflow_id": "wf-2",
            "objective": "retry",
            "steps": [{"id": "risky", "capability": "test.fail", "max_attempts": 3, "on_failure": "escalate"}],
        })
        result = WorkflowRunner(dispatch).run(plan)
        self.assertEqual(result.status, "escalated")
        self.assertEqual(result.steps["risky"].attempts, 3)
        self.assertEqual(len(attempts), 3)

    def test_condition_can_skip_step(self):
        plan = WorkflowPlan.from_dict({
            "workflow_id": "wf-3",
            "objective": "conditional",
            "steps": [
                {"id": "flag", "capability": "test.flag", "input": {}},
                {"id": "optional", "capability": "test.optional", "depends_on": ["flag"], "condition": "${flag.run}"},
            ],
        })
        result = WorkflowRunner(lambda task: {"status": "passed", "result": {"run": False}}).run(plan)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.steps["optional"].status, "skipped")

    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            WorkflowPlan.from_dict({
                "workflow_id": "wf-4",
                "objective": "cycle",
                "steps": [
                    {"id": "a", "capability": "x", "depends_on": ["b"]},
                    {"id": "b", "capability": "x", "depends_on": ["a"]},
                ],
            })


if __name__ == "__main__":
    unittest.main()
