# AEGIS Autonomous Web and App Builder

The builder is a governed AEGIS capability for producing and verifying a static website or dependency-free installable web app inside an assigned agent workspace.

## Execution pipeline

```text
User objective
  -> Planner
  -> Capability Resolution
  -> Security / Policy
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

This provides a deterministic foundation for the next builder stages: requirements intake, component generation, framework-aware builds, browser testing, visual verification, self-audit, and evidence capture.

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
  --description "Capture small tasks locally."
```

The command runs the governed `builder.run` action and returns create, build, self-test, and artifact evidence. It writes to `.jarvis/builds` by default and does not publish externally.
