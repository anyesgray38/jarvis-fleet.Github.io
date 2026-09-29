# AEGIS Second Brain

The knowledge runtime on port `8892` is AEGIS's local second brain. It keeps
small, searchable packets in active memory and stores complete source text in
the authenticated archive volume. Scraped text is treated as untrusted data;
it is never interpreted as an instruction or granted a tool.

## Department growth

`config/knowledge_departments.json` defines the inbound research stations.
Each plan has a manager, a designated `search_command`, capability ownership,
Wiki topics, Firecrawl search queries, direct URLs, and a cadence. The
scheduler runs bounded due-work cycles so one noisy source cannot consume the
whole research budget. Existing environment topic and URL lists are added to
Web Intelligence for backward compatibility.

Every fetched source passes the same learning loop before promotion:

```text
fetch -> structure -> extract claims -> extract concepts -> verify provenance
      -> compact -> promote to active memory -> archive full source
```

The reverse-engineering stage is local and deterministic. It extracts headings,
claims, concepts, links, code-block signals, fingerprints, and provenance
metadata without executing source content or treating webpage instructions as
AEGIS commands. A packet is not promoted when provenance verification fails.
Each cycle records the stage counts and each promoted packet records its
pipeline evidence in `reverse_engineering` and `promotion` fields.

## Retrieval

Agents can query local packets through the authenticated service:

```text
GET /search?q=deployment+security&department=security&limit=8
GET /search?q=deployment&full=1
GET /departments
```

Results are local evidence packets with title, source URL, department, manager,
summary, version, content hash, and archive reference. Full source retrieval is
explicit with `full=1` and remains bounded. The CLI exposes the same path:

```text
python3 -m jarvis knowledge search "deployment security" --department security
python3 -m jarvis knowledge departments
python3 -m jarvis knowledge research
```

## Continuous research

The scheduler performs one startup cycle and then checks every
`AEGIS_KNOWLEDGE_INTERVAL_MINUTES`. Research can also be triggered through the
authenticated `POST /research` endpoint with `{"force": true}`. Each cycle
records departments, packets, errors, and completion time. Re-fetching an
unchanged source updates its observation timestamp without creating fake growth;
changed content increments the packet version and emits a `source_changed`
event. Search results are cached locally and source pages are not fetched again
until `AEGIS_KNOWLEDGE_SOURCE_REFRESH_MINUTES` elapses. The hard
`AEGIS_KNOWLEDGE_MAX_EXTERNAL_CALLS` budget applies to Firecrawl search and
scrape calls per cycle, so local recall remains available even when external
research is paused or unavailable.

Firecrawl is admitted through AEGIS's existing MCP fabric at
`https://mcp.firecrawl.dev/v2/mcp`. Set `FIRECRAWL_API_KEY` or
`FIRECRAWL_OAUTH_TOKEN` only in the untracked deployment environment. A raw
value from an MCP config can also be supplied as `FIRECRAWL_AUTHORIZATION`;
the adapter normalizes it to a Bearer header. The credential is never stored in
the repository or returned to the dashboard.


## Durable agent memory with Hindsight

AEGIS can run a self-hosted Hindsight backend without replacing the evidence-oriented second brain. The existing knowledge runtime remains responsible for provenance, source archives, deterministic compaction, and bounded research. The optional memory profile adds:

- `hindsight` on loopback port `8895` for structured long-term memory.
- `memory-runtime` on loopback port `8894` as AEGIS's authenticated facade.
- Bank-scoped retain, recall, reflect, and MCP access.
- A persistent `aegis-hindsight` volume.

Start it with a local Ollama model already installed on the host:

```bash
AEGIS_MEMORY_TOKEN="$(openssl rand -hex 32)"
export AEGIS_MEMORY_TOKEN
export AEGIS_HINDSIGHT_LLM_PROVIDER=ollama
export AEGIS_HINDSIGHT_LLM_MODEL=llama3.2:3b  # change to an installed Ollama model

docker compose --env-file deploy/.env -f deploy/compose.yml --profile memory up -d hindsight memory-runtime
```

The Hindsight service uses `network_mode: host` so it can reach the host Ollama runtime at its normal loopback address. Both Hindsight and the AEGIS facade bind to loopback; they are not exposed to the LAN.

Authenticated AEGIS calls:

```text
POST /retain   {"bank_id":"aegis-core","content":"...","context":"..."}
POST /recall   {"bank_id":"aegis-core","query":"..."}
POST /reflect  {"bank_id":"aegis-core","query":"..."}
GET  /mcp      # returns the bank-scoped Hindsight MCP endpoint
GET  /health
```

Recommended bank layout: `aegis-core`, `coding:<repo>`, `agent:<name>`, `trading`, `prospecting`, and `finance`. Keep externally scraped evidence in the knowledge runtime; retain verified conclusions, agent experiences, decisions, outcomes, and repository/session history in Hindsight.
