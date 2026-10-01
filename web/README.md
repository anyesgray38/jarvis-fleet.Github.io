# AEGIS Control Center

Production web control plane for AEGIS Fleet. The UI is intentionally separate from the Python execution plane and contains no credentials or direct network credentials.

## Run

`npm install && npm run dev`

## Live connection

The dashboard reads telemetry through the server-side `/api/control-plane` proxy. Set `AEGIS_ORCHESTRATOR_URL` to the orchestrator HTTP API base URL, for example `http://127.0.0.1:8888` when running on the AEGIS host.

The proxy reads `/health`, `/agents`, and `/jobs` and never exposes the upstream URL or credentials to browser JavaScript. If the variable is absent or the upstream is unreachable, the dashboard explicitly shows a disconnected state instead of inventing telemetry.

## Governed Chromium control

The server-side `/api/browser` route uses `playwright-core` to attach to an
already-running Chromium CDP endpoint. It exposes `GET` status and the
bounded `POST` actions `goto`, `click`, `type`, `screenshot`, and
`disconnect`. The endpoint must be loopback-only; navigation allows HTTPS and
loopback HTTP, and password/secret fields remain blocked by AEGIS policy.

Browser control is opt-in and disabled by default. To enable it in the web
service, set `AEGIS_BROWSER_CONTROL_ENABLED=true` and point
`AEGIS_CHROME_CDP_URL` at a loopback endpoint such as
`http://127.0.0.1:9222`. Also set a strong, server-side
`AEGIS_BROWSER_CONTROL_TOKEN`; every browser-control request must include it
as `Authorization: Bearer <token>`. Launch Chromium with a separate profile:

```bash
google-chrome --remote-debugging-port=9222 \
  --user-data-dir=/run/user/1000/aegis-chrome
```

The CDP browser session is kept outside the repository and is never sent to
client-side JavaScript. The route is intended for the governed AEGIS agent
surface, not for exposing raw CDP to a browser.

## Shark After Dark business operations

The `Shark Ops` workspace is an optional server-side integration with the Shark After Dark API. Set `SHARK_API_URL` to the private API service URL and `SHARK_ADMIN_KEY` to the matching server-side admin key. The browser only talks to `/api/shark`; it never receives the admin key or calls the Shark API directly.

The workspace exposes booking pipeline, revenue summaries, service mix, security configuration posture, and governed appointment-status updates. Aegis assistance receives a verified snapshot as context and remains local-only by default. Payments, refunds, customer messaging, and destructive workflows are intentionally not enabled by this integration.

For remote access, the dashboard is served from the AEGIS host and reached over the private Tailscale network. The orchestrator remains private and is not directly exposed to browsers. Do not put Tailscale credentials, orchestrator secrets, or agent secrets in client-side environment variables.

## Deployment

The supported deployment model is a self-hosted Next.js production server on the AEGIS Linux host, supervised locally and accessed through Tailscale.

Example:

`npm run build`

`AEGIS_ORCHESTRATOR_URL=http://127.0.0.1:8888 npm start -- -H 0.0.0.0 -p 3000`

Then access the control center from an enrolled Tailscale device using the host's Tailscale address and port `3000`.
