# Coding Skill

READ → MAP → UNDERSTAND → PLAN → IMPLEMENT → TEST → REVIEW → REMEMBER.

Before substantial edits, AEGIS must build a repository model rather than treating code as disconnected text.

For complex code:
1. Inventory tracked source, configuration, tests, workflows, and entrypoints.
2. Extract symbols, imports, module boundaries, and test relationships deterministically where possible.
3. Select task-relevant files by objective, symbols, imports, entrypoints, and neighboring tests.
4. Reconstruct control flow, data flow, state ownership, external interfaces, invariants, failure paths, and concurrency boundaries before editing.
5. Separate observed facts from inferred architecture. Verify important inferences against source or executable tests.
6. Make the smallest coherent change that preserves existing contracts unless replacement is intentional.
7. Run targeted tests, then broader regression checks.
8. Review the final diff independently and verify changed-line claims.
9. Store durable architectural decisions, recurring defects, and verified lessons in project memory; do not store unverified guesses as facts.

A large context window is not a substitute for repository understanding. Prefer structured maps plus focused source over blindly concatenating the repository.
