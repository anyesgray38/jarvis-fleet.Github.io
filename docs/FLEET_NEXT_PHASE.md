# Fleet next phase

This phase establishes the control-plane primitives. It intentionally does not attempt to discover or mutate the operator's live Tailscale network.

Next integration points:

1. Authenticated node enrollment.
2. Tailscale-aware health provider.
3. Remote execution transport with request signing.
4. Capability attestation from each worker.
5. Per-node MCP and LocalAI inventories.
6. Evidence correlation across node, task, tool, and model.
7. Independent verification on a separate trusted node when risk warrants it.

The live device configuration must remain deployment-local and must never be committed with credentials, auth keys, or private node state.
