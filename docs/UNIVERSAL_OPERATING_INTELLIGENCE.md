# Universal operating intelligence — issue #55

## Doctrine

AGENTS.md defines responsibilities. SOPs define procedures. Policies define permissions. Evaluations establish whether outcomes meet criteria. CI/CD validates and releases changes to versioned artifacts; it is not the workflow for every ordinary task.

UNDERSTAND -> CLASSIFY -> PLAN -> AUTHORIZE -> EXECUTE -> EVALUATE -> RECOVER -> LEARN.

## Phase 1: architecture and gaps

Inspected AGENTS.md, architecture/autonomy documentation, runtime/CLI, action fabric, capability registry/router, policy/safety, evidence, discovery promotion, upgrade engine, tests and all five CI workflows before implementation. Baseline: 205 unittest tests pass; existing SQLite ResourceWarnings are present. The working tree already contains model/chat/AWS/local-Qwen changes, which are outside this issue.

| Requirement | Reuse | Missing vertical-slice behavior |
| --- | --- | --- |
| Interpret / discover | `CapabilityRegistry`, `SkillRouter` | Domain-independent activity classification and explicit success criteria |
| SOP | Existing skills describe reusable procedures | Versioned selection, provisional status and review gates |
| Governance | `Dispatcher`, `Policy`, `SafetyController`, `AutonomyController` | Trusted capability effects, plan-bound approvals and resource budgets |
| Evaluation | `audit_result`, registered dispatcher checks | Task-specific measurable criteria and CI applicability explanations |
| Execute / recover | `WorkflowPlan`, `WorkflowRunner` | Preserve trust through workflows, never retry authorization denial, escalate safely |
| Knowledge / audit | `MemoryStore`, `EvidenceStore` | Epistemic separation and evaluation-bound verified lessons |
| Improvement | `SelfUpgradeEngine`, `RollbackRegistry` | Baseline comparison, monitored promotion and explicit rollback lifecycle |
| Interface / CI | Existing CLI, unittest and pytest workflows | Non-executing planning command and bounded local read vertical slice |

Important boundaries: registered capability names alone do not establish permissions; objective text must not grant authority. Existing CLI `_run` fabricates a default successful scan, so the new entry point must not reuse that behavior. Existing workflow steps omit trust and retry rejected dispatches; fix those seams without replacing the executor. Existing upgrade protection must also protect governance files.

## Phased implementation plan

1. **Inspection / baseline:** map existing components and preserve unrelated edits (complete).
2. **Contracts / planning:** strict task/policy contracts, versioned SOP registry, capability discovery, evaluation and CI/CD selection. Test unknown domains, invalid inputs, selection and provisional procedures.
3. **Governed vertical slice:** build existing workflows, enforce plan-bound review, allowlists and existing policy/safety, bound retries/calls/time, evaluate results and record evidence-backed lessons. Test denial, stale approvals, failures and provenance; demonstrate a local file read using the existing action fabric.
4. **Improvement / regression:** reuse upgrade/rollback primitives for tested, compared, approved promotion and monitoring; add governance regression tests; run unittest, pytest and CLI smoke checks.

No production deployment, cloud compute, hosted model calls, GitHub writes, commits or pushes are part of this implementation. Keep changes in separable modules/tests for review.

## Status

Implementation in progress. Final verification and limitations will be recorded here.
