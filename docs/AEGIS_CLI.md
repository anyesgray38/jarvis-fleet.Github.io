# AEGIS CLI

The AEGIS CLI is the simplest operator surface for the system. You describe what
you want in normal language; AEGIS turns the request into an explicit plan using
the registered capabilities and refuses to invent capabilities.

## Quick start

From the repository root:

```bash
./bin/aegis health
./bin/aegis capabilities
./bin/aegis agents
./bin/aegis "inspect the repository and explain what should change"
```

The natural-language command is equivalent to `aegis run "..." `.

## Commands

- `health` — check the model runtime and orchestrator.
- `capabilities` — show the approved capability catalog.
- `agents` — show connected fleet agents.
- `jobs` / `job ID` — inspect queued and completed work.
- `chat "..." ` — normal AEGIS conversation.
- `plan "..." ` — create a structured implementation plan.
- `run "..." ` — natural-language planning entry point.
- `shell AGENT_ID "..." ` — explicitly address a connected agent.
- `broadcast "..." ` — explicitly broadcast a command to tagged/all agents.
- `queue HOSTNAME "..." ` — queue work for a host.

## Operator model

The CLI intentionally separates **understanding** from **execution**:

```text
Natural language
      |
      v
AEGIS planner
      |
      v
Registered capabilities
      |
      v
Explicit plan
      |
      v
Governed execution
      |
      v
Tests / evidence / verification
```

This is designed so an operator does not need to know Python, HTTP APIs,
agent IDs, model providers, or internal service names.

The CLI has no third-party Python dependency; it uses the standard library and
the existing AEGIS model/orchestrator HTTP surfaces.

## Important design rule

Natural language never becomes arbitrary tool selection. The planner must select
a capability already present in `capabilities/registry.json`. Missing information
is surfaced as a question/note rather than silently guessed.

Execution should remain behind the existing AEGIS policy, evidence, and
verification boundaries.
