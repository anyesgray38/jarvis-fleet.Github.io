import json

from jarvis.capabilities import CapabilityRegistry
from jarvis.dispatcher import Dispatcher
from routing import SkillRouter
from security.policy import Policy


def _components(tmp_path):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps({"capabilities": [
        {"id": "core.website_generation", "provider": "aegis", "kind": "core", "tags": ["website", "coding"], "verification": ["browser_check"]},
        {"id": "security.web_assessment", "provider": "aegis", "kind": "security", "tags": ["security", "assessment", "web"], "verification": ["scope_check"]}
    ]}))
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({"default": {"require_security_scan": True, "max_risk_score": 50, "blocked_severities": ["HIGH", "CRITICAL"]}}))
    skills = tmp_path / "skills"; (skills / "website-operation").mkdir(parents=True)
    return CapabilityRegistry(registry_path), Policy(policy_path), SkillRouter(registry_path, skills)


def _security():
    return {"execution_successful": True, "risk_score": 0, "severity": "LOW", "approved": True}


def test_dispatcher_routes_objective_before_policy_and_execution(tmp_path):
    registry, policy, router = _components(tmp_path); seen = []
    dispatcher = Dispatcher(registry, policy, lambda task, capability: seen.append((task, capability)) or {"ok": True}, router=router)
    result = dispatcher.dispatch({"task_id": "r-1", "objective": "build website", "verification": {"required": False}}, security=_security())
    assert result.status == "passed"
    assert seen[0][0]["capability"] == "core.website_generation"
    assert seen[0][0]["route"]["skill"] == "website-operation"


def test_explicit_capability_bypasses_router(tmp_path):
    registry, policy, router = _components(tmp_path); seen = []
    dispatcher = Dispatcher(registry, policy, lambda task, capability: seen.append(task) or {"ok": True}, router=router)
    result = dispatcher.dispatch({"task_id": "r-2", "capability": "core.website_generation", "objective": "security assessment", "verification": {"required": False}}, security=_security())
    assert result.status == "passed"
    assert seen[0]["capability"] == "core.website_generation"
    assert "route" not in seen[0]


def test_unmatched_objective_fails_closed(tmp_path):
    registry, policy, router = _components(tmp_path)
    dispatcher = Dispatcher(registry, policy, lambda *_: {"ok": True}, router=router)
    result = dispatcher.dispatch({"task_id": "r-3", "objective": "zyxwv unrelated", "verification": {"required": False}}, security=_security())
    assert result.status == "rejected"
    assert "no registered capability" in result.error
