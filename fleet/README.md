# AEGIS Fleet

The `fleet` package is the network-aware scheduling layer for distributed AEGIS workers.

- `node.py` — explicit worker identity, trust, status, and capability inventory.
- `policy.py` — fail-closed network constraints, including exit-node and public-bind controls.
- `scheduler.py` — deterministic capability-aware node selection.
- `registry.json` — operator-level overlay defaults; it intentionally contains no device addresses or credentials.

Tailscale is a transport/provider choice. AEGIS never treats overlay membership as authorization.
