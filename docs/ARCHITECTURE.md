# Jarvis Architecture

## Mission

Jarvis is a domain-agnostic AI operating system/control plane. It must not be designed around logistics, trading, games, or any single domain.

The core coordinates cognition, planning, orchestration, security, capabilities, execution, memory, interfaces, evidence, and verification. Specialized repositories remain independent domain brains and are exposed to Jarvis through capability manifests/contracts.

## System model

> Jarvis is the operating system. Agents are workers. Tools are instruments. Domain repositories are specialized brains. Memory is its institutional knowledge. Verification is its immune system. `jarvis-fleet` is its nervous system/execution fabric.

```text
USER
  -> INTERFACE
  -> COGNITIVE CORE
  -> PLANNER / ORCHESTRATOR
  -> SECURITY + POLICY
  -> CAPABILITY RESOLUTION
  -> AGENT DISPATCH
  -> EXECUTION FABRIC
  -> EVIDENCE
  -> INDEPENDENT VERIFICATION
  -> SELF-AUDIT
  -> RESULT / RETRY / ESCALATION
```

## Core subsystems

### Cognition
Understands the user's objective, constraints, context, and desired outcome. Produces a structured objective rather than immediately executing commands.

### Planning and orchestration
Converts objectives into task graphs, dependencies, priorities, retries, and escalation paths. Multi-agent work is first-class.

### Capability system
A generic registry answers what Jarvis can do and which implementation can do it. Capabilities are not synonymous with repositories; repositories are implementations/providers of capabilities.

Examples include logistics, trading research, software engineering, web research, game processing, media, finance, and future capabilities.

### Security and policy
Every execution crosses explicit trust boundaries:

1. Supply-chain admission: is the skill/repository trustworthy?
2. Capability authorization: is this agent authorized for the capability?
3. Execution policy: is this specific operation permitted?
4. Result policy: is the result sufficiently verified?

NVIDIA SkillSpector is an external security scanner/admission component. It remains an upstream dependency rather than being copied into this repository.

### Execution fabric
`jarvis-fleet` provides controlled execution across workers, machines, containers, and other runtimes. Low-level execution remains separate from domain logic.

### Memory
Memory is a first-class subsystem with separate concerns for episodic history, semantic knowledge, procedural knowledge, project state, and evidence/provenance.

### Evidence
Every meaningful task should produce traceable evidence: task identity, capability, implementation/ref, agent, inputs, outputs, timestamps, verification results, and audit state.

### Verification and self-audit
Agents do not get to declare their own work correct. Whenever practical, verification is independent of execution. Failed verification triggers diagnosis/replanning/retry or escalation.

```text
PLAN
  -> SECURITY CHECK
  -> EXECUTE
  -> COLLECT EVIDENCE
  -> VERIFY
  -> SELF-AUDIT
      -> PASS: PUBLISH
      -> FAIL: DIAGNOSE -> REPLAN -> RETRY
                       -> ESCALATE after repeated failure
```

## Domain separation

Specialized repositories remain independent. Jarvis should integrate them through capability contracts instead of duplicating their domain architectures.

Current examples:

- `anyesgray38/shark-logistics` — logistics capability
- `HTML5GameArchive/gfiles` — game/archive capability
- Shark SMC Engine — trading/research capability; exact repository identifier must be resolved before making it authoritative in the registry

These are plugins/capability providers, not the definition of Jarvis itself.

## Repository direction

Target structure:

```text
jarvis-fleet/
├── core/
│   ├── orchestrator/
│   ├── planner/
│   ├── dispatcher/
│   └── scheduler/
├── agents/
│   ├── runtime/
│   ├── worker/
│   ├── browser/
│   ├── research/
│   └── coding/
├── capabilities/
├── security/
├── verification/
├── evidence/
├── memory/
├── interfaces/
├── contracts/
├── projects/
└── tests/
```

This structure is a target, not a requirement to move everything at once. Existing working components should be evolved incrementally with tests and compatibility preserved.

## Engineering rule

For every new subsystem, ask: **Does this belong to Jarvis's universal control plane, or does it belong to a specialized capability?** Universal behavior belongs in Jarvis. Domain-specific behavior belongs in the domain repository.

All future architecture changes should preserve this separation and strengthen the full Jarvis control loop rather than optimizing for one domain.
