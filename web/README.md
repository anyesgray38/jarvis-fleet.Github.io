# AEGIS Control Center

Production web control plane for AEGIS Fleet. The UI is intentionally separate from the Python execution plane and contains no credentials or direct Tailscale access.

## Run

`npm install && npm run dev`

## Live connection

The dashboard reads telemetry through the server-side `/api/control-plane` proxy. Set `AEGIS_ORCHESTRATOR_URL` to the orchestrator HTTP API base URL, for example `http://127.0.0.1:8888` when running locally.

The proxy reads `/health`, `/agents`, and `/jobs` and never exposes the upstream URL or credentials to browser JavaScript. If the variable is absent or the upstream is unreachable, the dashboard explicitly shows a disconnected state instead of inventing telemetry.

For a remote deployment, expose the orchestrator through an authenticated, private gateway reachable by the web server. Do not put Tailscale credentials, orchestrator secrets, or agent secrets in client-side environment variables.

## Deploy

Configure Vercel with the repository root directory set to `web`, framework preset `Next.js`, and build command `npm run build`. Add `AEGIS_ORCHESTRATOR_URL` as a server-side environment variable for the deployment environment.
