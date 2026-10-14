# AEGIS Qwen inference deployment proposal

Prepared 2026-10-09. Status: awaiting approval for new paid compute and its quota request. No cloud resources were changed by this proposal.

## Chat implementation and verification

The companion code change adds `/chat` and a control-center link, checks model availability before enabling Send, and displays the actual response route. Compose pins the proposed Qwen alias and `localai` provider; the model stays unroutable pending deployment verification. `AEGIS_ALLOW_EXTERNAL_INFERENCE` defaults to `false`: the runtime does not construct the OpenAI provider even if a key exists, and rejects requests attempting to enable external inference. The web chat proxy also forces self-hosted-only requests. These controls cover model inference; other separately configured integrations are not represented as free or disabled.

Local verification: 205 Python tests passed (SQLite resource warnings were emitted); TypeScript type checking passed; Playwright UI checks passed for disconnected/connected states, disabled Send, self-hosted request flags, reply display and model-route display. UI replies were mocked, so this is not evidence that Qwen can generate a real response. The first browser test hit a cold-development-build timeout; it passed after compilation, and its navigation budget now allows 60 seconds.

Existing-control-plane update is separate from the paid-worker proposal. A scoped remote update completed successfully: inference/chat files applied, 22 targeted tests passed, production Next.js build passed, and only web/model-runtime were recreated. No new EC2 capacity was launched.

Independent remote verification succeeded: both services healthy, `/chat` HTTP 200, `/api/chat` returns the exact pinned Qwen alias with `ready: false`, zero loaded models and `external_inference_enabled: false`. A direct request attempting to enable OpenAI was rejected with HTTP 400 and `External paid inference is disabled on this AEGIS deployment`. This confirms deployed safeguards, not working Qwen inference. The private chat URL is intentionally omitted from this public repository. The browser UI was tested locally; the deployed HTTP endpoints were tested on the AWS host because this executor could not connect through the private access path.

The cloud build used its cached Next.js 16.4.0 dependency installation; the workstation has 16.3.6. Production compilation/type checking passed. A later local type check exposed a malformed generated development validator; the temporary development server was stopped and the generated file preserved outside the project before regenerating route types. No application source was removed.

## Operator selection and observed state

The operator selected the Qwen release already pushed to AWS. The local workstation still uses `huihui-qwen3.5-9b-abliterated:q2_k`; that is not the selected replacement.

- Account: operator-managed AWS account; region: `us-east-2`.
- Source: https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF
- Artifacts: private S3 model prefix configured at deployment time.
- S3 listing confirms the quantized weights, projector, manifests, checksums and upload completion marker. No multipart uploads remain. File contents have not yet been downloaded and independently hashed for inference deployment.
- Existing control plane: operator-managed `m7i-flex.large`, 7.6 GiB reported RAM, no swap. A remote verification command returned success.
- On that host, `/v1/models` returns an empty list, and `/health` on port 8891 reports `ready: false`. Ollama is not running there. The only EC2 instance returned in this region was the control plane.
- Smallest uploaded full-model quant: IQ2_M, 10,319,906,944 bytes. Proposed Q4_K_P: 17,923,393,664 bytes. The control-plane host cannot keep even the smallest full model resident alongside the stack.

## Concrete proposal

Create one separate, operator-owned `g6.xlarge` inference worker in the existing AEGIS VPC in Ohio. AWS pricing describes 4 vCPUs, 16 GiB system RAM and one GPU with 24 GB memory. Use Q4_K_P, a current Qwen-compatible llama.cpp CUDA server, one inference slot and an initial 8,192-token context. Memory fit and speed remain estimates until tested. Start text-only, without the optional FastMTP sidecar or vision projector.

Serve alias `HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF:Q4_K_P` over the existing OpenAI-compatible provider adapter. The corresponding model registry entry is deliberately `routable: false` until verified. Registration alone does not switch the running service.

Use encrypted 80 GiB gp3 EBS, an instance role limited to reading this model prefix plus SSM access, and private inference access from the AEGIS control plane. No public inference or SSH ingress. Use the existing private access mechanism for workstation requests. Do not treat the publisher's speed measurements as benchmarks for this hardware.

## Cost and quota gate

AWS Pricing `GetProducts` for Linux/shared/on-demand `g6.xlarge` in `us-east-2`, retrieved 2026-10-09, SKU `NES344FTJTVN47RU`, effective 2026-10-01: **$0.8048 per running hour**. That is $19.3152 per 24-hour day or $587.504 per 730-hour month, compute only. EBS, network, public IPv4 if needed for egress, and existing services are additional. Stopping the worker ends instance compute billing but does not remove EBS charges.

Service Quotas `L-DB2E81BA` (Running On-Demand G and VT instances) is **0 vCPUs**. One worker needs at least **4 vCPUs**. Obtain approval for the cost, request the quota increase, and wait for approval before launch. Account plan restrictions and regional capacity must also be checked; a quota increase does not guarantee launch availability.

## Activation and verification sequence

1. Confirm paid-worker approval; request G/VT quota of 4 vCPUs.
2. When eligible, deploy the isolated worker using an immutable compatible runtime build; download only the selected quant and verify against the signed release manifest/checksum.
3. Check GPU availability, memory usage, model loading and `/v1/models` alias.
4. Send a bounded real inference request and inspect its response, timing and failure behavior.
5. Set the AEGIS provider endpoint to this private worker, enable the verified model entry and make it the selected default. Verify through AEGIS `/chat`, including the returned model route, rather than only calling the backend.
6. Resume the ICT 2022 mentorship study with its existing source inventory and progress tracking. Evaluate source grounding and chart-reading requirements separately.

Rollback: preserve the original provider configuration and registry, revert the endpoint/model selection if validation fails, and stop only the new worker to contain compute charges. Never delete the S3 model release or existing control-plane data.
