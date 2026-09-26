# AEGIS Autonomous Web and App Builder

The builder is a governed AEGIS capability for producing and verifying a static website or dependency-free installable web app inside an assigned agent workspace. It turns a request into a validated design brief and composes allow-listed interactive features.

## Execution pipeline

```text
User objective
  -> Planner
  -> Capability Resolution
  -> Security / Policy
  -> Design brief / feature selection
  -> builder.run
  -> Isolated Workspace
  -> project.create
  -> project.build
  -> project.test
  -> Evidence / Preview
```

## Safety boundary

The builder is intentionally an allow-listed generator and verifier, not an unrestricted coding shell. It:

- writes only beneath the supplied AEGIS workspace;
- rejects absolute paths and traversal;
- validates project names and user-facing fields;
- limits generated output size;
- does not install packages, fetch remote assets, or execute arbitrary commands;
- requires explicit `overwrite=true` before changing a non-empty project directory.

Package installation, browser automation, Git writes, and deployment are separate capabilities and must pass their own policy and verification gates.

## Generated project

The `website` kind produces a dependency-free static project containing:

- `index.html`
- `styles.css`
- `script.js`
- `README.md`

Supported functions include contact capture, booking requests, quote requests, newsletter capture, FAQ accordions, calculators, and local task lists. These demonstrate real browser behavior and persist only to local storage; production email, CRM, payments, scheduling, and authenticated data services remain separately authorized integrations.

The design brief is written to `aegis.design.json` and returned as evidence. AEGIS never treats user text or model output as executable source; only the allow-listed modules can be composed.

The `app` kind produces an installable web-app starter containing:

- `index.html` — accessible app shell and form
- `styles.css` — responsive styling
- `app.js` — local browser-storage behavior
- `app.webmanifest` — install metadata
- `README.md` — generated project notes

Run it locally from the repository root:

```bash
python3 -m jarvis builder task-app --kind app \
  --title "Task App" \
  --description "Capture small tasks locally." \
  --feature task_list
```

The command runs the governed `builder.run` action and returns create, build, self-test, and artifact evidence. It writes to `.jarvis/builds` by default and does not publish externally.
