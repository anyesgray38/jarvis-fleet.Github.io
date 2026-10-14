import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from jarvis.autonomy import MemoryStore, TrustLevel
from jarvis.capabilities import CapabilityRegistry
from jarvis.cli import main
from jarvis.dispatcher import Dispatcher
from jarvis.evaluation import EvaluationEngine, KnowledgeLedger, Metric, cicd_selection
from jarvis.operating import ApprovalLedger, OperatingEngine, local_read_engine, task_contract
from jarvis.procedures import Procedure, SOPRegistry
from jarvis.workflow import WorkflowPlan, WorkflowRunner
from security.policy import Policy
from security.safety import SafetySettings


class OperatingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls, self.events = [], []
        self.time = 0
        self.registry_path = self.root / "caps.json"
        self.registry_path.write_text(json.dumps({"capabilities": [{
            "id": "test.inspect", "action": "test.inspect", "tags": ["inspect"], "verification": ["independent"]
        }]}))
        policy_path = self.root / "policy.json"
        policy_path.write_text(json.dumps({"default": {"require_security_scan": False}}))
        self.dispatcher = Dispatcher(CapabilityRegistry(self.registry_path), Policy(policy_path), self.executor,
                                     checks={"independent": lambda task, result: (result.get("ok") is True, "checked")},
                                     safety=SafetySettings(self.root / "safety.json"))
        self.policy = {"version": 1, "max_attempts": 3, "max_calls": 4, "max_seconds": 120,
                       "capabilities": {"test.inspect": {"effect": "read", "trust": 0, "idempotent": True,
                                                         "controls": [], "action": "test.inspect"}}}
        self.sops = SOPRegistry([Procedure("inspect", 1, "inspect", ("test.inspect",), ("Observe and evaluate.",),
                                          "reviewed", ("tests.test_operating",))])
        self.engine = OperatingEngine(self.dispatcher, policy=self.policy, sops=self.sops,
                                      allowed_capabilities=frozenset({"test.inspect"}), evidence=self.events,
                                      clock=lambda: self.time)

    def executor(self, task, capability):
        self.calls.append(deepcopy(task))
        return {"ok": True, "count": 3, "secret": "do-not-log-me"}

    def task(self, **overrides):
        return {"task_id": "task-1", "objective": "Inspect cryogenic violin archive evidence", "capability": "test.inspect",
                "criteria": [{"name": "count", "field": "count", "operator": "at_least", "expected": 3}], **overrides}

    def test_unknown_domains_use_effect_not_domain(self):
        for domain in ("cryogenic violins", "orbital gardening", "ceramic acoustics"):
            plan = self.engine.plan(self.task(objective=f"Inspect {domain}"))
            self.assertEqual(plan["activity"], "inspect")
            self.assertFalse(plan["cicd"]["applicable"])
            self.assertEqual(plan["blockers"], [])
            self.assertIn("not domain", plan["classification_reason"])

    def test_unknown_or_ambiguous_capability_never_executes(self):
        plan = self.engine.plan(self.task(capability="", objective="Understand glorpification"))
        self.assertTrue(plan["blockers"])
        self.assertEqual(plan["sop"]["status"], "provisional")
        self.assertEqual(self.engine.run(plan)["status"], "blocked")
        self.assertFalse(self.calls)

    def test_discovery_uses_existing_router(self):
        self.assertEqual(self.engine.plan(self.task(capability=""))["capability"], "test.inspect")

    def test_sop_latest_version_and_immutable_versions(self):
        p = Procedure("inspect", 2, "inspect", ("test.inspect",), ("Improved observation.",), "reviewed", ("regression-2",))
        self.sops.add(p)
        self.assertEqual(self.engine.plan(self.task())["sop"]["version"], 2)
        with self.assertRaises(ValueError): self.sops.add(p)

    def test_provisional_requires_plan_bound_review(self):
        self.engine.sops = SOPRegistry()
        plan = self.engine.plan(self.task())
        self.assertEqual(self.engine.run(plan)["status"], "blocked")
        self.assertFalse(self.calls)
        token = self.engine.approvals.grant(plan["fingerprint"], actor="operator")
        self.assertEqual(self.engine.run(plan, approval=token)["status"], "passed")
        self.assertEqual(self.engine.run(plan, approval=token)["status"], "blocked")

    def test_stale_approval_cannot_authorize_changed_plan(self):
        self.engine.sops = SOPRegistry()
        plan = self.engine.plan(self.task())
        token = self.engine.approvals.grant(plan["fingerprint"], actor="operator")
        changed = self.engine.plan(self.task(input={"different": True}))
        self.assertEqual(self.engine.run(changed, approval=token)["status"], "blocked")
        plan["task"]["input"] = {"tampered": True}
        self.assertEqual(self.engine.run(plan, approval=token)["status"], "blocked")
        self.assertFalse(self.calls)

    def test_expired_approval_and_task_authority_injection(self):
        ledger = ApprovalLedger(clock=lambda: self.time)
        token = ledger.grant("plan", actor="operator", ttl_seconds=1)
        self.time = 2
        with self.assertRaises(PermissionError): ledger.consume(token, "plan")
        with self.assertRaises(ValueError): task_contract(self.task(approved=True))
        with self.assertRaises(ValueError): task_contract(self.task(criteria=[]))
        with self.assertRaises(ValueError): task_contract(self.task(max_attempts=True))

    def test_approval_does_not_override_safety_or_existing_policy(self):
        self.engine.policy["capabilities"]["test.inspect"]["controls"] = ["external_network"]
        plan = self.engine.plan(self.task())
        token = self.engine.approvals.grant(plan["fingerprint"], actor="operator")
        self.assertEqual(self.engine.run(plan, approval=token)["status"], "blocked")
        self.engine.policy["capabilities"]["test.inspect"]["controls"] = []
        self.dispatcher.policy.data["default"]["require_security_scan"] = True
        self.assertEqual(self.engine.run(self.engine.plan(self.task()))["status"], "blocked")
        self.assertFalse(self.calls)

    def test_untrusted_action_substitution_is_blocked(self):
        self.dispatcher.registry.get("test.inspect")["action"] = "shell.execute"
        self.assertTrue(self.engine.plan(self.task())["blockers"])

    def test_missing_checks_and_resource_overrides_fail_closed(self):
        self.assertTrue(self.engine.plan(self.task(max_attempts=4))["blockers"])
        self.assertTrue(self.engine.plan(self.task(max_attempts=2, max_calls=1))["blockers"])
        self.engine.policy["capabilities"]["test.inspect"]["idempotent"] = False
        self.assertTrue(self.engine.plan(self.task(max_attempts=2))["blockers"])
        self.dispatcher.checks.clear()
        self.assertTrue(self.engine.plan(self.task())["blockers"])

    def test_all_artifact_types_select_cicd_but_do_not_launch_it(self):
        for kind in ("code", "prompt", "model", "configuration", "workflow"):
            selected = cicd_selection(kind)
            self.assertTrue(selected["applicable"])
            self.assertTrue(selected["checks"])
            plan = self.engine.plan(self.task(artifact_kind=kind))
            self.assertEqual(plan["activity"], "change")
            self.assertTrue(plan["blockers"])  # missing independent suite adapters
        self.assertFalse(self.calls)

    def test_verified_execution_and_audit_redaction(self):
        result = self.engine.run(self.engine.plan(self.task()))
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["verified"])
        self.assertEqual(result["lesson"]["kind"], "verified_fact")
        self.assertNotIn("do-not-log-me", json.dumps(self.events))
        self.assertIn("operating.evaluated", [e["event"] for e in self.events])

    def test_metric_failure_cannot_be_learned_as_success(self):
        self.dispatcher.executor = lambda task, cap: {"ok": True, "count": 1}
        result = self.engine.run(self.engine.plan(self.task()))
        self.assertEqual(result["status"], "escalated")
        self.assertFalse(result["verified"])
        self.assertNotIn("lesson", result)
        self.assertFalse(any(k.startswith("verified_fact:") for k in self.engine.knowledge.memory.snapshot()["knowledge"]))

    def test_bounded_transient_retry_and_unknown_failure_escalation(self):
        def flaky(task, cap):
            self.calls.append(task)
            if len(self.calls) == 1: raise RuntimeError("temporary timeout")
            return {"ok": True, "count": 3}
        self.dispatcher.executor = flaky
        self.assertEqual(self.engine.run(self.engine.plan(self.task(max_attempts=2)))["status"], "passed")
        self.assertEqual(len(self.calls), 2)
        self.calls.clear()
        def failed(task, cap):
            self.calls.append(task)
            raise RuntimeError("unrecognized failure")
        self.dispatcher.executor = failed
        self.assertEqual(self.engine.run(self.engine.plan(self.task(task_id="new", max_attempts=3)))["status"], "escalated")
        self.assertEqual(len(self.calls), 1)

    def test_time_budget_overrun_is_not_success_or_retried(self):
        def slow(task, cap):
            self.time += 70
            return self.executor(task, cap)
        self.dispatcher.executor = slow
        result = self.engine.run(self.engine.plan(self.task(max_attempts=2)))
        self.assertEqual(result["status"], "escalated")
        self.assertEqual(len(self.calls), 1)

    def test_epistemic_provenance_cannot_be_faked(self):
        ledger = self.engine.knowledge
        for kind in ("assumption", "hypothesis", "unknown"):
            ledger.note(kind, "Not yet verified", kind=kind, source="operator")
        with self.assertRaises(ValueError): ledger.note("x", "False fact", kind="verified_fact", source="model")
        with self.assertRaises(KeyError): ledger.learn("invented-report")
        report = self.engine.evaluator.evaluate("x", "test", (), {}, audit_passed=True, evidence_ref="ref")
        report["passed"] = True
        with self.assertRaises(ValueError): ledger.learn(report["id"])

    def test_numeric_metrics_reject_bool_nan_and_missing_fields(self):
        metric = Metric("n", "nested.n", "at_least", 1)
        for result in ({}, {"nested": {"n": True}}, {"nested": {"n": float("nan")}}):
            self.assertFalse(metric.check(result)["passed"])

    def test_workflow_preserves_trust_and_never_retries_denial(self):
        calls = []
        plan = WorkflowPlan.from_dict({"workflow_id": "wf", "objective": "test", "steps": [
            {"id": "one", "capability": "test.inspect", "trust_required": 4, "max_attempts": 3, "on_failure": "escalate"},
            {"id": "two", "capability": "test.inspect"}]})
        def denied(task):
            calls.append(task)
            return {"status": "rejected", "error": "authorization denied"}
        result = WorkflowRunner(denied).run(plan)
        self.assertEqual(calls[0]["trust_required"], 4)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.steps["two"].status, "skipped")
        with self.assertRaises(ValueError): WorkflowPlan.from_dict({"workflow_id": "empty", "objective": "test", "steps": []})


class LocalVerticalSliceTests(unittest.TestCase):
    def test_real_local_read_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("unseen domain: glass harmonicas")
            engine = local_read_engine(root, evidence=[], safety=SafetySettings(root / "safety.json"))
            task = {"task_id": "read", "objective": "Inspect glass harmonica notes", "capability": "terminal.read",
                    "input": {"path": "note.txt"}, "criteria": [{"name": "content", "field": "content", "operator": "contains", "expected": "harmonicas"}]}
            self.assertEqual(engine.run(engine.plan(task))["status"], "passed")
            task.update(task_id="escape", input={"path": "../outside"})
            self.assertEqual(engine.run(engine.plan(task))["status"], "escalated")

    def test_cli_plans_without_writes_then_executes_existing_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.txt").write_text("hello")
            task = root / "task.json"
            task.write_text(json.dumps({"task_id": "cli", "objective": "Inspect the note", "capability": "terminal.read",
                "input": {"path": "note.txt"}, "criteria": [{"name": "text", "field": "content", "operator": "equals", "expected": "hello"}]}))
            output = io.StringIO()
            argv = ["--json", "--safety-config", str(root / "safety.json"), "operate", str(task), "--workspace", str(root)]
            with contextlib.redirect_stdout(output): self.assertEqual(main(argv), 0)
            self.assertEqual(json.loads(output.getvalue())["activity"], "inspect")
            self.assertFalse((root / ".jarvis").exists())
            output = io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(main([*argv, "--execute"]), 0)
            self.assertTrue(json.loads(output.getvalue())["verified"])
            self.assertTrue((root / ".jarvis/operating.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
