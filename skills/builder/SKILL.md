# Autonomous Web and App Builder

Use this skill when the objective is to create a website or a dependency-free installable web app, including requests for real browser functions.

## Procedure

1. Validate the project name, kind, user-facing title, description, requested features, and assigned workspace.
2. Build a serializable design brief from the request; use only allow-listed feature modules.
3. Run the governed `builder.run` action.
4. Inspect the returned design, create, build, and self-test evidence.
5. Stop at the private workspace artifact unless deployment is separately authorized.

## Supported outputs

- `website`: responsive static HTML, CSS, JavaScript, and README.
- `app`: installable web-app starter with a manifest, local browser storage, HTML, CSS, JavaScript, and README.

Allow-listed functions: `contact_form`, `booking`, `quote_request`, `newsletter`, `faq`, `calculator`, and `task_list`.

## Boundaries

- Files stay inside the assigned workspace.
- Existing non-empty projects require explicit overwrite approval.
- Generated projects do not fetch remote assets, install packages, execute arbitrary commands, or publish externally.
- Deployment, Git writes, package installation, and browser automation remain separate governed actions.

## Verification

The builder must return evidence for the generated files, size, required structure, local assets, viewport metadata, semantic main content, title, and app accessibility checks where applicable.

## Failure handling

If a stage fails, preserve the error and workspace path, do not claim success, and retry only after the failing input or project state is corrected.
