# AEGIS Second Brain

The knowledge runtime on port `8892` is AEGIS's local second brain. It keeps
small, searchable packets in active memory and stores complete source text in
the authenticated archive volume. Scraped text is treated as untrusted data;
it is never interpreted as an instruction or granted a tool.

## Department growth

`config/knowledge_departments.json` defines the inbound research stations.
Each plan has a manager, Wiki topics, Firecrawl search queries, direct URLs,
and a cadence. The scheduler runs bounded due-work cycles so one noisy source
cannot consume the whole research budget. Existing environment topic and URL
lists are added to Web Intelligence for backward compatibility.

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
