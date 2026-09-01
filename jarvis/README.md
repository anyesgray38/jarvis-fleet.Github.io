# Jarvis Control Plane

`jarvis-fleet` is the execution substrate. The control plane adds a stable task contract, capability registry, and self-audit boundary so specialized repositories can remain independent.

## Integrated capabilities

- `logistics.route_plan` -> `anyesgray38/shark-logistics`
- `trading.smc_research` -> Shark SMC Engine
- `archive.game_processing` -> `HTML5GameArchive/gfiles`

## Execution contract

1. Receive a task.
2. Resolve the capability.
3. Select an eligible fleet agent.
4. Execute without changing the task definition.
5. Collect result and evidence.
6. Run required verification checks.
7. Reject, retry, or publish based on the audit report.

The fleet agent remains a low-level executor. Domain logic belongs in the specialized repository.
