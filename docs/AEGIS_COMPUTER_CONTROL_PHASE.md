# AEGIS Computer-Control Phase

The Linux target is now a deliberately small execution profile. The full
repository remains the source snapshot on GitHub, while
`deploy/linux-computer-control.json` declares what belongs on the Linux host
for this phase.

## Active surface

The active path is:

```text
operator objective
  -> orchestrator / MCP bridge
  -> desktop runtime :8894 (loopback only)
  -> CUA driver
  -> screen, accessibility, and bounded input
  -> fresh observation and verification
```

The active roster is limited to orchestration, computer operation, terminal
inspection, authorized web operation, browser diagnostics, safety, testing,
and independent verification. Trading and business-prospecting agents are
archived, not loaded by the Linux profile.

## Live baseline on this host

Observed directly during the rebuild:

- `127.0.0.1:8894` is already supervised by the desktop runtime service.
- The CUA driver is present and reports a `1371x771` display.
- A harmless pointer move completed and `pointer_at` verification returned
  `satisfied: true`.
- Safety gates are active; sensitive typing is blocked by policy.
- Full screenshot capture and accessibility are currently degraded. The CUA
  driver sees only its cursor overlay and reports an X11 capture error. The
  running Chromium process is using Wayland; the Wayland/X11 mismatch is the
  current working diagnosis, not a confirmed root cause.

## Acceptance criteria

Computer control is considered usable only when all of these are evidenced:

1. Fresh desktop observation returns a real target window or accessibility
   tree, not only the cursor overlay.
2. A bounded action changes the target state.
3. A separate verification predicate confirms the expected transition.
4. Screenshot or accessibility evidence is retained when the task requires
   visual confirmation.
5. Stop, sensitive-field, and failure paths remain fail-closed.

## Reproducible browser target

Start a browser that the X11 fallback can observe:

```bash
AEGIS_BROWSER_CDP_PORT=9222 ./scripts/start_control_browser.sh about:blank
```

The launcher keeps its profile outside the repository, forces X11, disables
GPU initialization, and leaves sandboxing enabled by default. Set
`AEGIS_BROWSER_NO_SANDBOX=1` only when the host requires it.

## Cleanup boundary

The Linux profile excludes repository caches, virtual environments, browser
profiles, build outputs, trading, prospecting, discovery, knowledge, fleet,
provider, and web UI components. Those remain outside the execution bundle or
are retained only in the full GitHub source snapshot.
