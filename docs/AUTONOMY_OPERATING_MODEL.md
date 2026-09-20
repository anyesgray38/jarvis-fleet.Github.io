# Jarvis Autonomy Operating Model

Jarvis now treats every unit of work as a governed task rather than a loose command.

## Control flow

OBJECTIVE -> TASK ID -> PLAN -> AUTHORIZE -> QUEUE -> EXECUTE -> VERIFY -> PUBLISH

Failures enter the Failure Doctor, which can recommend bounded retry, provider failover, replanning, or escalation. It does not silently widen permissions.

## Trust levels

1. OBSERVE
2. SUGGEST
3. PREPARE
4. EXECUTE_LOCAL
5. EXECUTE_EXTERNAL
6. AUTONOMOUS

A task may require a higher level than the current controller. Dry-run simulation reports what would happen without executing it.

## Memory

Memory is separated into personal, project, procedural, knowledge, and evidence layers. Evidence is never treated as ordinary memory.

## Capability contracts

Capabilities describe inputs, outputs, permissions, risk, verification, rollback, and requirements. Provider/tool selection is an implementation detail behind the contract.

## Recovery

Failures are classified into transient, provider availability, verification, and unknown classes. Recovery is bounded and escalates when the safe retry budget is exhausted.

## Human control

External execution remains gated by the trust level. Rollback handlers are explicit rather than assumed.

## Phase completion

This operating model covers the control-plane foundation, autonomy controls, memory, capability contracts, recovery, scheduling/queue interfaces, observability, simulation, and rollback primitives. Domain-specific brains can plug into the same contracts without duplicating governance.
