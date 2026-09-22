# AEGIS Fleet

The `fleet` package is the network-aware scheduling layer for distributed AEGIS workers.

- `node.py` — explicit worker identity, trust, status, and capability inventory.
- `auth.py` — bootstrap-signed enrollment plus replay-resistant HMAC request verification.
- `attestation.py` — signed worker capability attestation and trust promotion.
- `health.py` — read-only Tailscale status health provider.
- `transport.py` — policy-gated signed remote execution transport.
- `inventory.py` — bounded MCP and LocalAI inventory snapshots.
- `evidence.py` — cross-node/task/tool/model evidence hash chain.
- `independent.py` — distinct verified-node result verification.
- `policy.py` — fail-closed network constraints, including exit-node and public-bind controls.
- `scheduler.py` — deterministic capability-aware node selection.
- `registry.json` — operator-level overlay defaults; it intentionally contains no device addresses or credentials.

Tailscale is a transport/provider choice. AEGIS never treats overlay membership as authorization.
New nodes are admitted as `untrusted` with attestation pending; enrollment does not grant execution trust.
