# AEGIS Skill Router

AEGIS has a deterministic routing layer inspired by the reusable architectural pattern in reverse-skill: classify an objective against a capability catalog, select a relevant reusable skill, then leave execution to the existing governed action fabric.

The implementation is native to AEGIS. It does not copy reverse-skill's security toolchain or create a second capability system.

## Flow

OBJECTIVE -> ROUTER -> CAPABILITY -> SKILL -> POLICY/AUTHORIZATION -> ACTION FABRIC -> EVIDENCE -> VERIFICATION

## Boundaries

- Routing has no execution side effects.
- A route never grants permission.
- Security routes are marked as requiring authorization and remain subject to the existing fail-closed scope policy.
- Unknown objectives return no route rather than inventing a capability.
- Verification requirements come from the existing capability registry.
- Skills are discovered from the existing skills directories.

This gives AEGIS progressive disclosure: the apex agent can narrow a large tool/capability surface before loading procedural detail, while preserving existing evidence, memory, policy, and verification layers.
