# Fleet next phase

This phase establishes the control-plane primitives. It intentionally does not attempt to discover or mutate the operator's live Tailscale network.

Implemented in the current control-plane pass:

1. Authenticated node enrollment with bootstrap HMAC signatures.
2. Replay-resistant signed request verification with bounded timestamps.
3. Read-only Tailscale-aware health snapshots.
4. Signed, policy-gated remote execution transport.
5. Capability attestation that promotes nodes only after verification.
6. Bounded per-node MCP and LocalAI inventories with deterministic digests.
7. Hash-chained evidence correlation across node, task, tool, and model.
8. Independent verification on a distinct verified node.

The remaining work is deployment-local adapter wiring: connect the injected
transport sender to the chosen private protocol and connect the inventory and
evidence primitives to live worker services. Those adapters must remain local
to the deployment and must not add credentials or private node state here.

The live device configuration must remain deployment-local and must never be committed with credentials, auth keys, or private node state.
