# AEGIS Control Center

Production web control plane for AEGIS Fleet. The UI is intentionally separate from the Python execution plane and contains no credentials or direct network credentials.

## Run

`npm install && npm run dev`

## Live connection

The dashboard reads telemetry through the server-side `/api/control-plane` proxy. Set `AEGIS_ORCHESTRATOR_URL` to the orchestrator HTTP API base URL, for example `http://127.0.0.1:8888` when running on the AEGIS host.

The proxy reads `/health`, `/agents`, and `/jobs` and never exposes the upstream URL or credentials to browser JavaScript. If the variable is absent or the upstream is unreachable, the dashboard explicitly shows a disconnected state instead of inventing telemetry.

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
