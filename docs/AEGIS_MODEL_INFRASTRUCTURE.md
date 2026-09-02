# AEGIS Model Infrastructure

AEGIS treats model runtimes as infrastructure providers. They are replaceable implementations behind a provider-neutral model routing layer and are not part of the AEGIS cognitive core.

## LocalAI

`localai` is the first supported local inference provider.

- Transport: OpenAI-compatible HTTP
- Default endpoint: `http://127.0.0.1:8080/v1`
- Adapter: `providers/localai.py`
- Provider registry: `capabilities/providers.json`
- Capability: `core.model_inference`

LocalAI can therefore provide local model execution while AEGIS remains responsible for objective understanding, planning, policy, capability resolution, agent dispatch, evidence, verification, and self-audit.

## Routing principle

The model router should select providers from policy-approved candidates based on task constraints. AEGIS should be able to add providers such as Ollama, vLLM, hosted models, or other runtimes without changing the cognitive core.

Example policy progression:

```text
Task
  -> security/policy
  -> model constraints
  -> approved providers
  -> model router
  -> inference provider
  -> evidence
  -> verification
```

For sensitive tasks, policy may prefer local inference. A provider being local does not make its output trusted; model output still enters the normal evidence and verification pipeline.

## Boundary rule

Do not move planning, authorization, verification, memory policy, or orchestration into LocalAI. Consume LocalAI through the provider contract instead.
