# AEGIS Discovery Engine

The Discovery Engine turns research objectives into governed, testable knowledge. It is domain-agnostic and deliberately separates generation from truth.

```text
Objective
  -> Hypothesis + null hypothesis
  -> Falsification criteria
  -> Experiment design
  -> Governed execution capability
  -> Observation + evidence
  -> Statistical analysis
  -> Anomaly / contradiction detection
  -> Independent reproduction
  -> Verification
  -> Conservative knowledge promotion
```

## Epistemic states

`idea -> hypothesis -> testable -> observed -> reproduced -> verified`

Alternative terminal states are `rejected` and `conflicted`.

A generated idea is never treated as a discovery merely because a model produced it.

## Unknown discovery

The subsystem explicitly looks for signals that current knowledge is incomplete:

- expectation mismatches
- numerical outliers
- independent contradictions
- reproduction mismatches
- undeclared dependencies
- distribution shifts

These signals become investigation candidates rather than being silently discarded.

## Scientific safeguards

Experiments require a null hypothesis and falsification criteria. Results retain evidence provenance and independent groups. Promotion requires verification, sufficient confidence, evidence, and independent support. Statistical helpers are screening primitives, not universal scientific inference.

## Execution boundary

The Discovery Engine does not execute arbitrary generated code. Simulation, code generation, laboratory tooling, browser operations, and other execution remain separate AEGIS capabilities behind the normal security, policy, evidence, and verification gates.

This permits AEGIS to investigate areas such as algorithms, programming languages, AI architectures, physics simulations, mathematical conjectures, and other domains without turning the research planner into an unrestricted execution authority.
