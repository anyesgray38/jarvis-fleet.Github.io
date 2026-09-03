# AEGIS Control Center

Production web control plane for AEGIS Fleet. The UI is intentionally separate from the Python execution plane and contains no credentials or direct network credentials.

## Run

`npm install && npm run dev`

## Live connection

The dashboard reads telemetry through the server-side `/api/control-plane` proxy. Set `AEGIS_ORCHESTRATOR_URL` to the orchestrator HTTP API base URL, for example `http://127.0.0.1:8888` when running on the AEGIS host.

The proxy reads `/health`, `/agents`, and `/jobs` and never exposes the upstream URL or credentials to browser JavaScript. If the variable is absent or the upstream is unreachable, the dashboard explicitly shows a disconnected state instead of inventing telemetry.

For remote access, the dashboard is served from the AEGIS host and reached over the private Tailscale network. The orchestrator remains private and is not directly exposed to browsers. Do not put Tailscale credentials, orchestrator secrets, or agent secrets in client-side environment variables.

## Deployment

The supported deployment model is a self-hosted Next.js production server on the AEGIS Linux host, supervised locally and accessed through Tailscale.

Example:

`npm run build`

`AEGIS_ORCHESTRATOR_URL=http://127.0.0.1:8888 npm start -- -H 0.0.0.0 -p 3000`

Then access the control center from an enrolled Tailscale device using the host's Tailscale address and port `3000`.
