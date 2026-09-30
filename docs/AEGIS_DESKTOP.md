# AEGIS desktop control

`core.desktop_control` is implemented by the loopback-only
`aegis-desktop-runtime` in [`desktop_runtime.py`](../desktop_runtime.py). The
runtime is deliberately a separate host process: the model can request a
bounded observation or action, but it cannot import OS-control libraries or
run arbitrary commands.

The control ladder is:

1. CUA/accessibility state when the host can provide it.
2. A browser/application-specific semantic target when a caller supplies one.
3. Screenshot/vision evidence when capture is available.
4. Coordinates as the last resort.

The service exposes:

- `GET /health` — backend, permission, safety, and stop-latch state.
- `GET /observe` — screen, pointer, windows, and accessibility summary.
- `GET /screenshot?include_image=true` — bounded base64 PNG when capture works.
- `POST /action` — `move`, `click`, `double_click`, `right_click`, `scroll`,
  `type`, `hotkey`, `drag`, and bounded `wait`.
- `POST /verify` — bounded predicates, never arbitrary code.
- `POST /stop` — emergency stop, always allowed.
- `POST /resume` — requires `confirm=true` and `desktop_control` enabled.

Start it locally:

```bash
cd /home/anyesgray38/jarvis-fleet
python3 desktop_runtime.py
```

Or install the user service template:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/aegis-desktop-runtime.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now aegis-desktop-runtime.service
```

Input is fail-closed. Enable it only when the operator is ready:

```bash
python3 -m jarvis.cli safety enable desktop_control
python3 -m jarvis.cli desktop status
python3 -m jarvis.cli desktop stop --reason "operator emergency stop"
```

Password and secret fields remain blocked. Sudo prompts, payments, file
deletion, and security changes require both their own safety switch and
`confirm=true`. Every action is written to `.jarvis/desktop_audit.jsonl` with
typed text redacted. Moving the real pointer into the configured top-left
8x8-pixel corner latches the runtime stopped; configure the corner with
`AEGIS_DESKTOP_KILL_CORNER` and `AEGIS_DESKTOP_KILL_CORNER_SIZE`.

The Hermes MCP bridge exposes `desktop_observe`, `desktop_screenshot`,
`desktop_action`, `desktop_verify`, `desktop_stop`, and `desktop_resume`. Set
`AEGIS_DESKTOP_RUNTIME_URL` if the service uses a non-default loopback port.

## Direct Chrome command

AEGIS can also control an already-connected Chrome session directly from the
terminal without Hermes. Chrome must expose a local DevTools endpoint, usually
by starting it with `--remote-debugging-port=9222`:

```bash
python3 -m jarvis.cli chrome bedtime-music
```

Use `--cdp-url` or `AEGIS_CHROME_CDP_URL` for another endpoint, `--target` to
select a tab, and `--min-minutes` / `--max-minutes` to change the duration
window. The command is gated by `desktop_control`, navigates only to YouTube,
and verifies that the selected video is actively playing before it succeeds.

The host can be degraded without the service being broken. For example, on a
Wayland/XWayland session the CUA driver may report screen dimensions and a
pointer while screenshot capture or AT-SPI is unavailable. AEGIS receives
that state explicitly and must re-observe or recover rather than guessing.

## Chrome diagnostics agent

The read-only Chrome Diagnostician checks the local DevTools endpoint,
browser-process presence, and executable availability without starting,
stopping, or modifying a browser:

```bash
python3 -m jarvis.cli diagnose chrome
```

Use `--json` for machine-readable evidence, `--cdp-url` for a non-default
DevTools endpoint, or `--browser-binary` when the browser executable is not on
`PATH`. The capability is registered as `core.chrome_diagnostics` and routes to
the debugging skill for governed agent workflows.

### Browser sanitation boundary

Browser content is untrusted data. AEGIS validates that CDP remains loopback
only, restricts the governed YouTube workflow to HTTPS results/watch URLs,
canonicalizes video links, bounds page-derived text, and ignores non-YouTube or
duplicate result rows. Playwright profiles and reports should remain outside
the repository; `.venv/`, `.firecrawl/`, `playwright-report/`, `test-results/`,
and browser state files are ignored by the build.
