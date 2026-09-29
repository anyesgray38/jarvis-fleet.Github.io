# Hermes Agent ↔ AEGIS

Hermes is the operator-facing conversation layer. AEGIS remains the governed
control plane for capability routing, safety controls, fleet dispatch,
verification, evidence, and deployment boundaries.

## Local MCP bridge

`hermes_mcp_server.py` is a dependency-free stdio MCP server. Hermes loads it
from `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  aegis:
    command: "python3"
    args: ["/absolute/path/to/jarvis-fleet/hermes_mcp_server.py"]
    cwd: "/absolute/path/to/jarvis-fleet"
    tools:
      include: [aegis_status, aegis_capabilities, aegis_plan, aegis_inspect, aegis_audit,
                aegis_read_file, aegis_search, aegis_job, aegis_queue]
```

The bridge exposes:

- `aegis_status` — live orchestrator, worker, job, and safety state.
- `aegis_capabilities` — registered capability metadata.
- `aegis_plan` — deterministic routing without execution.
- `aegis_inspect` — repository-local file and directory shape.
- `aegis_audit` — read-only Python syntax checking.
- `aegis_read_file` — bounded UTF-8 reads inside the repository, excluding credential-shaped files.
- `aegis_search` — bounded plain-text search without shell execution.
- `aegis_job` — inspect one orchestrator job.
- `aegis_queue` — queue a worker command only when `confirm=true` and the persisted
  `raw_fleet` safety control is explicitly enabled.

## Boundary

The bridge does not expose credentials, unrestricted host shell, filesystem
writes, live trading, or deployment. Worker queueing is a narrow interaction
surface and remains fail-closed behind the AEGIS `raw_fleet` safety control.

To verify the bridge independently:

```bash
python3 -m unittest tests.test_hermes_mcp_server -v
```
