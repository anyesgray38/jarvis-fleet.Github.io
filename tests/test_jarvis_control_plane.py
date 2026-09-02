import json

from jarvis.audit import audit_result
from jarvis.capabilities import CapabilityRegistry
from jarvis.dispatcher import Dispatcher
from security.policy import Policy, PolicyDenied
from security.skillspector import admit, parse_result


def _registry(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"capabilities": [{"id": "test.echo", "tags": ["test"]}]}))
    return CapabilityRegistry(path)


def _policy(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"default": {"require_security_scan": True, "max_risk_score": 50, "blocked_severities": ["HIGH", "CRITICAL"]}}))
    return Policy(path)


def test_skillspector_fail_closed_on_incomplete():
    decision = admit({"execution_successful": False, "risk_score": 0, "severity": "LOW"})
    assert decision.approved is False


def test_skillspector_accepts_low_risk_complete_result():
    decision = admit({"execution_successful": True, "risk_score": 12, "severity": "LOW", "approved": True})
    assert decision.approved is True


def test_skillspector_parser_rejects_non_object():
    try:
        parse_result("[]")
    except Exception:
        return
    assert False, "expected parser failure"


def test_policy_rejects_missing_security_result(tmp_path):
    policy = _policy(tmp_path)
    try:
        policy.authorize("test.echo")
    except PolicyDenied:
        return
    assert False, "expected policy denial"


def test_dispatcher_executes_and_audits(tmp_path):
    registry = _registry(tmp_path)
    policy = _policy(tmp_path)
    task = {
        "task_id": "t-1",
        "capability": "test.echo",
        "input": {"value": "ok"},
        "verification": {"required": True, "checks": ["result_ok"]},
    }
    dispatcher = Dispatcher(
        registry,
        policy,
        lambda task, capability: {"ok": True, "value": task["input"]["value"]},
        checks={"result_ok": lambda task, result: (result.get("ok") is True, "result ok")},
    )
    result = dispatcher.dispatch(task, security={"execution_successful": True, "risk_score": 0, "severity": "LOW", "approved": True})
    assert result.status == "passed"
    assert result.audit["passed"] is True


def test_dispatcher_rejects_failed_audit(tmp_path):
    dispatcher = Dispatcher(
        _registry(tmp_path),
        _policy(tmp_path),
        lambda task, capability: {"ok": False},
        checks={"result_ok": lambda task, result: (False, "bad result")},
    )
    task = {"task_id": "t-2", "capability": "test.echo", "input": {}, "verification": {"required": True, "checks": ["result_ok"]}}
    result = dispatcher.dispatch(task, security={"execution_successful": True, "risk_score": 0, "severity": "LOW", "approved": True})
    assert result.status == "rejected"
    assert result.audit["passed"] is False
