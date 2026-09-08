# AEGIS always-on deployment

This deployment separates the AEGIS control plane from any single laptop, Penguin/Crostini VM, or Tailscale network.

## Architecture

```text
Internet
   |
   | optional Cloudflare Tunnel
   v
web :3000
   |
   +--> orchestrator :8888 (private Docker network)
   |       +--> fleet TLS :4444 (not published)
   |
   +--> model-runtime :8891 (private Docker network)
           |
           +--> LM Studio / LocalAI on host or remote worker

Persistent Docker volumes:
  aegis-evidence
  aegis-certs
```

The public surface is only the Next.js control center. The orchestrator API, fleet listener, and model runtime are not published as host ports.

## VPS / always-on host

1. Install Docker Engine + Compose on an always-on Linux VPS or server.
2. Clone this repository.
3. Copy `deploy/.env.example` to `.env` and set `AEGIS_FLEET_SECRET` to a long random value.
4. Start the private control plane:

```bash
docker compose -f deploy/compose.yml up -d --build
```

The control center will be available on port `3000` of the host.

For a public HTTPS endpoint without opening inbound ports, create a Cloudflare Tunnel whose public hostname targets `http://web:3000`, then start the optional tunnel profile:

```bash
docker compose -f deploy/compose.yml --profile public up -d
```

Set `CLOUDFLARE_TUNNEL_TOKEN` in `.env` before starting that profile.

## Model strategy

The model runtime is deliberately separate from the web application. It can use:

- LM Studio on the deployment host (`host.docker.internal:1234` by default)
- LocalAI on the deployment host (`host.docker.internal:8080` by default)
- A reachable remote model worker by overriding `AEGIS_LMSTUDIO_URL` or `AEGIS_LOCALAI_URL`

This means the always-on control plane does not need to carry a large model. GPU-heavy inference can remain on a separate worker and be added later without moving the dashboard.

## Operational properties

- `restart: unless-stopped` on every core service
- health checks for web, orchestrator, and model runtime
- evidence persisted in a Docker volume
- fleet certificates persisted in a Docker volume and generated on first start
- no public host ports for orchestrator/fleet/model services
- optional public ingress through Cloudflare Tunnel
- no dependency on Tailscale for public access
- no dependency on Penguin/Crostini for production uptime

## Future GitOps layer

Kubernetes/K3s and ArgoCD are intentionally not required for the first always-on deployment. Once the control plane is stable, the same service boundaries can be promoted into a GitOps layer without forcing Kubernetes onto the minimal installation.
