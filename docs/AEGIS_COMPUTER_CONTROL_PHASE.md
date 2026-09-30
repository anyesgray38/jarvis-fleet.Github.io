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
- The Debian AT-SPI runtime is installed and `org.a11y.Bus` is active for the
  user session.
- A real X11 Chromium window was discovered with its pid/window id, and the
  accessibility result returned `degraded: false` with live elements.
- A native Wayland Chromium process launches with `--ozone-platform=wayland`,
  but the installed CUA driver does not discover that surface on this
  compositor; no native Wayland computer-control success is claimed.
- A harmless pointer move completed and `pointer_at` verification returned
  `satisfied: true`.
- Safety gates are active; sensitive typing is blocked by policy.
- Full-display capture can still fail on this XWayland session, so the runtime
  records and verifies a window-scoped PNG capture instead of labeling it as a
  desktop capture.
- The native CUA window enumerator can block while Chromium publishes
  accessibility state. The runtime therefore prefers bounded X11 discovery
  whenever a validated X11 window is present.
- This ChromeOS/Sommelier compositor does not expose the native Wayland
  toplevel, screencopy, or input protocols required by the installed CUA
  driver. Native Wayland is therefore the browser/CDP mode; governed
  screen-level control uses the explicit X11/XWayland fallback until a
  supported compositor adapter is available. Browser-specific CDP use still
  requires an independent endpoint health check.

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
AEGIS_BROWSER_PLATFORM=wayland AEGIS_BROWSER_CDP_PORT=9222 \
  ./scripts/start_control_browser.sh about:blank
```

The launcher keeps its profile outside the repository, uses native Wayland by
default, disables GPU initialization, and leaves sandboxing enabled by
default. Set `AEGIS_BROWSER_NO_SANDBOX=1` only when the host requires it.

For screen-level AEGIS control on this host, launch the browser through
XWayland explicitly:

```bash
AEGIS_BROWSER_PLATFORM=x11 AEGIS_BROWSER_CDP_PORT=9222 \
  ./scripts/start_control_browser.sh about:blank
```

The host also needs the AT-SPI runtime so element-level observation is
available. On Debian-based hosts, install `at-spi2-core`; the tracked user
service requests `at-spi-dbus-bus.service` automatically. Verify the session
bus with:

```bash
busctl --user list | grep org.a11y.Bus
```

## Cleanup boundary

The Linux profile excludes repository caches, virtual environments, browser
profiles, build outputs, trading, prospecting, discovery, knowledge, fleet,
provider, and web UI components. Those remain outside the execution bundle or
are retained only in the full GitHub source snapshot.
