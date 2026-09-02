# AEGIS Fleet Network Fabric

AEGIS Fleet treats private overlay networking as transport, not trust.
Tailscale is the first-class network provider because it gives AEGIS private node-to-node reachability, while AEGIS retains identity, capability, policy, execution, evidence, and verification ownership.

## Node lifecycle

```text
Discover node
  -> authenticate identity
  -> inventory capabilities
  -> verify health
  -> assign trust
  -> admit network permissions
  -> schedule workload
  -> execute
  -> record evidence
  -> independently verify
```

## Exit nodes

An exit node is represented as a routing constraint on a workload rather than a global implicit setting. Operators can allow exit-node routing and optionally maintain an allow-list. Public binds remain disabled by default.

```json
{
  "network": {
    "internet": true,
    "private_network": true,
    "exit_node": "approved-exit-node",
    "public_bind": false
  }
}
```

## Trust boundary

Being connected to the private overlay does not make a machine trusted. A remote worker must have explicit `trusted` or `verified` status before network execution is admitted. This prevents a compromised or newly joined node from inheriting Fleet privileges.

## Scheduling

The scheduler filters first on capability, status, labels, modalities, and network policy. It then ranks eligible nodes deterministically, preferring an explicitly selected node, verified nodes, and private-overlay connectivity.

The scheduler does not execute work. This preserves the AEGIS separation between planning, policy, dispatch, execution, and verification.

## MCP integration

The network fabric is designed to carry the existing MCP capability fabric:

```text
AEGIS Planner
    |
    v
Fleet Scheduler ----> verified node
    |                     |
    |                     +--> LocalAI
    |                     +--> MCP servers
    |                     +--> Browser workers
    |                     +--> Domain agents
    v
Evidence + Verification
```

MCP descriptions and outputs remain untrusted data. Network privacy never bypasses MCP admission or AEGIS policy.
