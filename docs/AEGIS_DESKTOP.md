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

The host can be degraded without the service being broken. For example, on a
Wayland/XWayland session the CUA driver may report screen dimensions and a
pointer while screenshot capture or AT-SPI is unavailable. AEGIS receives
that state explicitly and must re-observe or recover rather than guessing.
