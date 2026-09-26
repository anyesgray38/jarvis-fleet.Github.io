# AEGIS Tailscale-only deployment

This deployment keeps the AEGIS control plane private by default. The web application listens only on localhost and **Tailscale Serve is the default ingress**. There is no Cloudflare Tunnel, Funnel, or public hostname.

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
             ^
             |
       local governed worker

     localhost:8892
     knowledge-runtime

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

### Optional private-interface access

For a desktop on the host's private interface, set `AEGIS_WEB_BIND=0.0.0.0` in the untracked `deploy/.env` and install the included firewall guard:

```bash
sudo install -m 0644 deploy/aegis-firewall.nft /etc/aegis-firewall.nft
sudo install -m 0644 deploy/aegis-firewall.service /etc/systemd/system/aegis-firewall.service
sudo systemctl daemon-reload
sudo systemctl enable --now aegis-firewall.service
docker compose --env-file deploy/.env -f deploy/compose.yml up -d web
```

The guard allows port `3000` only from the configured private `/30` and loopback, while the authenticated gateway remains on loopback at `127.0.0.1:8877`. Do not enable this mode without the firewall guard. The current host's direct address is `http://100.115.92.26:3000`.

The model runtime also binds to localhost. LM Studio and LocalAI default to localhost on ports `1234` and `8080` respectively. Override their URLs in `deploy/.env` if inference runs on a separate worker.

## Business prospecting

The authenticated prospecting runtime listens on localhost `8893` and stores scans and prospect history in the persistent `aegis-prospecting` volume. The dashboard's Prospecting section and the CLI command below use the same workflow:

```bash
python3 -m jarvis business-scan "US-19 Thomaston Georgia" --max-results 10 --generate 1
```

The workflow records corridor evidence, normalizes duplicates, researches public websites and social profiles, audits observable HTML characteristics, assigns an explainable digital-opportunity score, and generates private concept pages only for qualified records. If Firecrawl MCP is unavailable or rate-limited, it falls back to bounded direct HTTP search/scraping where possible and reports the degradation; an empty fallback is never treated as proof that a website does not exist. Configure `AEGIS_PROSPECT_SOURCE_URLS` for known public municipal/chamber directories. Concept pages are explicitly marked as private demonstrations and are not published or sent to businesses automatically.

The knowledge runtime binds to localhost on port `8892`. Wikipedia search works without an external key. Firecrawl web intake uses the admitted official MCP endpoint; keyless use is bounded, while `FIRECRAWL_API_KEY` or `FIRECRAWL_OAUTH_TOKEN` can be set in the untracked `deploy/.env` for authenticated limits. Credentials are never sent to browser JavaScript. Department research policy lives in `config/knowledge_departments.json`; the runtime performs bounded due-work cycles, stores compact packets locally, archives full source text, and exposes authenticated `/search`, `/departments`, and `/research` endpoints. Legacy comma-separated `AEGIS_KNOWLEDGE_WIKI_TOPICS` and `AEGIS_KNOWLEDGE_WEB_SOURCES` are routed into Web Intelligence.

Knowledge is stored in the persistent `aegis-knowledge` volume. Active memory keeps compact distilled packets and metadata; full source text is archived separately and can only be retrieved through the authenticated knowledge service when needed.

The fleet listener uses port `4444`. If host firewall rules are enabled, allow it only on the Tailscale interface for trusted AEGIS fleet nodes.

The Compose deployment includes a non-root local worker connected to the fleet listener. It runs with `AEGIS_AGENT_UID`/`AEGIS_AGENT_GID`, has the repository mounted at `/workspace`, and is the execution node for governed dashboard tasks. Additional remote workers can connect with `agent.py` using the fleet certificate and secret.

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
