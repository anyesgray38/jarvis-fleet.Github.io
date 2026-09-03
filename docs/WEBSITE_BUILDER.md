# AEGIS Website Builder

The Website Builder is a governed AEGIS action for producing a static website project inside an assigned agent workspace.

## Execution pipeline

```text
User objective
  -> Planner
  -> Capability Resolution
  -> Security / Policy
  -> website.create
  -> Isolated Workspace
  -> Build / Test
  -> Browser Verification
  -> Independent Verification
  -> Self-Audit
  -> Evidence / Publish
```

## Safety boundary

`website.create` is intentionally a generator, not an unrestricted coding shell. It:

- writes only beneath the supplied AEGIS workspace;
- rejects absolute paths and traversal;
- validates project names and user-facing fields;
- limits generated output size;
- does not install packages or execute commands;
- requires explicit `overwrite=true` before changing a non-empty project directory.

Build tooling, package installation, browser automation, and deployment are separate capabilities and must pass their own policy and verification gates.

## Generated project

The first implementation produces a dependency-free static project containing:

- `index.html`
- `styles.css`
- `script.js`
- `README.md`

This provides a deterministic foundation for the next builder stages: requirements intake, component generation, framework-aware builds, browser testing, visual verification, self-audit, and evidence capture.
