import unittest

from upgrade.engine import SelfUpgradeEngine, UpgradeDenied, UpgradePolicy
from upgrade.models import UpgradePlan, UpgradeStage


class SelfUpgradeTests(unittest.TestCase):
    def plan(self, **kwargs):
        values = dict(
            upgrade_id="up-1",
            objective="improve planner",
            base_ref="master",
            files=("jarvis/planner.py", "tests/test_planner.py"),
            change_summary="add deterministic planning guard",
            tests=("python -m unittest",),
            require_human_approval=True,
        )
        values.update(kwargs)
        return UpgradePlan(**values)

    def test_requires_tests(self):
        with self.assertRaises(UpgradeDenied):
            SelfUpgradeEngine().admit(self.plan(tests=()))

    def test_protected_files_are_rejected(self):
        with self.assertRaises(UpgradeDenied):
            SelfUpgradeEngine().admit(self.plan(files=(".github/workflows/aegis-tests.yml",)))
        with self.assertRaises(UpgradeDenied):
            SelfUpgradeEngine().admit(self.plan(files=("orchestrator.py",)))

    def test_ready_requires_tests_and_audit(self):
        engine = SelfUpgradeEngine()
        staged = engine.stage(self.plan(), changed_bytes=1000)
        ready = engine.validate(staged, tests_passed=True, audit_passed=True)
        self.assertEqual(ready.stage, UpgradeStage.READY)

    def test_failed_tests_cannot_be_approved(self):
        engine = SelfUpgradeEngine()
        staged = engine.stage(self.plan(), changed_bytes=1000)
        failed = engine.validate(staged, tests_passed=False, audit_passed=True)
        approved = engine.approve(failed, True)
        self.assertFalse(approved.approved)
        self.assertEqual(approved.stage, UpgradeStage.REJECTED)

    def test_apply_requires_explicit_approval(self):
        engine = SelfUpgradeEngine()
        staged = engine.stage(self.plan(), changed_bytes=1000)
        ready = engine.validate(staged, tests_passed=True, audit_passed=True)
        rejected = engine.approve(ready, False)
        result = engine.execute_approved(rejected, apply=lambda _: "abc")
        self.assertFalse(result.approved)
        self.assertEqual(result.stage, UpgradeStage.REJECTED)

    def test_approved_upgrade_records_commit(self):
        engine = SelfUpgradeEngine()
        staged = engine.stage(self.plan(), changed_bytes=1000)
        ready = engine.validate(staged, tests_passed=True, audit_passed=True)
        approved = engine.approve(ready, True)
        result = engine.execute_approved(approved, apply=lambda _: "abc123")
        self.assertTrue(result.approved)
        self.assertEqual(result.commit_ref, "abc123")


if __name__ == "__main__":
    unittest.main()
