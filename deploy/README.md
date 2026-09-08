# AEGIS Tailscale-only deployment

This deployment keeps the AEGIS control plane private. The web application listens only on localhost and **Tailscale Serve is the only ingress**. There is no Cloudflare Tunnel, Funnel, public hostname, or public port mapping.

## Architecture

```text
                         TAILNET
                            |
                         iPhone
                            |
                     Tailscale Serve
                            |
                            v
                 localhost:3000 (web)
                            |
             +--------------+--------------+
             |                             |
             v                             v
     localhost:8888                 localhost:8891
     orchestrator                  model-runtime
             |
             +--> fleet TLS :4444

Persistent Docker volumes:
  aegis-evidence
  aegis-certs
```

Tailscale Serve exposes a local service to the tailnet while keeping it unavailable to the public internet. Tailscale's access-control policies also apply to the served service.

## Deploy

On the always-on Linux host:

1. Install Docker Engine + Compose.
2. Install and authenticate Tailscale.
3. Clone this repository.
4. Run:

```bash
bash deploy/tailscale-up.sh
```

The launcher:

- verifies Docker and Tailscale
- creates `deploy/.env` when needed
- generates `AEGIS_FLEET_SECRET` when needed
- builds and starts AEGIS with Docker Compose
- starts Tailscale Serve in the background
- prints the private HTTPS URL for the tailnet

Open the URL printed by `tailscale serve status` from your iPhone while the iPhone is connected to the same Tailscale tailnet.

## Important

Do **not** run `tailscale funnel`. Funnel is intentionally not part of this deployment.

Do not expose port `3000` through a router, cloud load balancer, or public firewall rule. The AEGIS web service is deliberately bound to `127.0.0.1`; Tailscale Serve is the ingress layer.

The model runtime also binds to localhost. LM Studio and LocalAI default to localhost on ports `1234` and `8080` respectively. Override their URLs in `deploy/.env` if inference runs on a separate worker.

The fleet listener uses port `4444`. If host firewall rules are enabled, allow it only on the Tailscale interface for trusted AEGIS fleet nodes.

## Model strategy

The always-on control plane does not need to carry a large model. GPU-heavy inference can remain on a separate worker and be routed through the existing provider/model fabric.

## Operational properties

- `restart: unless-stopped` on core services
- health checks for web, orchestrator, and model runtime
- evidence persisted in a Docker volume
- fleet certificates persisted in a Docker volume
- web ingress restricted to localhost + Tailscale Serve
- no Cloudflare Tunnel
- no Tailscale Funnel
- no public inbound endpoint
- no dependency on Penguin/Crostini for production uptime

## Future GitOps layer

Kubernetes/K3s and ArgoCD are intentionally not required for the first always-on deployment. The same service boundaries can be promoted into a GitOps layer later without changing the private access model.
