# AEGIS Control-Plane Boundary

## Two separate systems

### Remote Control Interface — Control Plane UI
The Next.js application provides the remote interface:

- navigation and dashboard
- chat surfaces
- task submission
- agent management
- telemetry
- evidence and verification views

Remote Control Interface does **not** connect directly to the AEGIS orchestrator or private Tailscale IPs.

### Linux — Execution Plane
The Linux host runs the actual AEGIS system:

- orchestrator
- agents
- MCP
- models
- memory
- security
- fleet execution
- homelab services

## Connection

```
Browser
  |
  v
Remote Control Interface AEGIS Control Center
  |
  | authenticated HTTPS/API
  v
AEGIS Gateway (Linux)
  |
  v
AEGIS Orchestrator
  |
  +--> Agents
  +--> MCP
  +--> Models
  +--> Memory
  +--> Homelab
```

The browser never receives the gateway token.

## Remote Control Interface environment

Set:

```text
AEGIS_GATEWAY_URL=https://your-authenticated-gateway
AEGIS_GATEWAY_TOKEN=<long-random-secret>
```

For UI-only testing, the Remote Control Interface deployment can use:

```text
AEGIS_DEMO_MODE=true
```

Demo mode makes the interface interactive but **does not execute commands on Linux**.

## Gateway contract

The Linux gateway should expose only the endpoints required by the dashboard:

- `GET /health`
- `GET /agents`
- `GET /jobs`
- `POST /queue`
- `POST /agents/:id/tag`
- `POST /agents/:id/pine`

Every request must require authentication. The gateway then talks to the private orchestrator locally.

## Security boundary

Do not expose:

- orchestrator port 8888 directly to the internet
- fleet TLS port 4444 directly to the internet
- Tailscale IPs in browser-side JavaScript
- gateway tokens to the client

The Remote Control Interface API route is server-side and adds the gateway authorization header before forwarding requests.
