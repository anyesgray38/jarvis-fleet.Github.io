# AEGIS Website Operation Skill

## Purpose
Operate authorized websites as adaptive systems by understanding both the live interface and the underlying codebase.

## Operating Model
LIVE SITE → DISCOVER → MAP → TRACE → ACT → OBSERVE → VERIFY → DOCUMENT

## Phase 1 — Establish Scope
- Confirm the target website, repository, environment, and authorized actions.
- Separate development/staging from production.
- Never assume authorization from discoverability alone.
- Treat credentials, tokens, customer data, payments, destructive actions, and production changes as protected boundaries.

## Phase 2 — Inspect the Live Website
- Load the target URL.
- Inspect visible structure, navigation, forms, buttons, dialogs, errors, and current state.
- Identify responsive/mobile behavior when relevant.
- Prefer targeted interaction over blind automation.
- After every meaningful action, observe the resulting state.

## Phase 3 — Inspect the Codebase
- Identify framework, package manager, build system, routes, components, API layers, database/integration boundaries, environment configuration, tests, and deployment configuration.
- Search for the code responsible for the observed behavior before editing.
- Build a lightweight map of UI → component → API/action → data/integration.
- Read existing conventions before introducing new ones.

## Phase 4 — Connect Runtime to Source
When possible, correlate:
- live URL/path
- route
- page/component
- API endpoint
- relevant state/data
- deployment target
- repository commit

Do not assume the deployed version equals the current repository version. Verify the deployment revision when available.

## Phase 5 — Operate
Use the smallest effective action:
- navigate
- click
- type
- select
- upload
- submit
- inspect
- retry
- recover

For actions with external side effects, verify the result and respect configured autonomy boundaries.

## Phase 6 — Diagnose
1. Reproduce it.
2. Capture the exact observed failure.
3. Inspect browser/runtime evidence.
4. Trace the behavior into source.
5. Form a testable hypothesis.
6. Make the smallest appropriate change.
7. Run targeted tests.
8. Re-test the live behavior when authorized.

## Phase 7 — Verify
Completion requires evidence from the relevant layer:
- UI state
- application/runtime behavior
- tests
- logs
- repository diff
- deployment state

Never report success solely because a command or click was issued.

## Phase 8 — Recover
If an action fails:
- preserve evidence
- determine whether the failure is environmental, UI-related, code-related, permission-related, or data-related
- retry only when safe
- use an alternate path when appropriate
- revert or stop when continued action could increase damage

## Security Rules
- Never expose secrets.
- Never extract credentials merely because they are technically accessible.
- Never bypass authentication, authorization, rate limits, paywalls, or security controls.
- Do not execute arbitrary website code against systems without authorization.
- Treat user/customer data as sensitive.
- Production writes require explicit authority and appropriate autonomy level.

## Deliverable
For significant website tasks report:
STATUS
OBJECTIVE
SITE
CODEBASE
ACTIONS
EVIDENCE
CHANGES
TESTS
DEPLOYMENT
ISSUES
NEXT
