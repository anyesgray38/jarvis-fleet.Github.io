# AEGIS Business Prospecting

The Business Prospecting Agent is a governed outbound capability for public business research and private website demonstrations.

## Workflow

```text
target → discover → normalize → location evidence → website/social research
       → deterministic audit → explainable score → SQLite memory
       → qualified concept page → static preview verification
```

The workflow is implemented in `prospecting/` and runs through the authenticated `prospecting-runtime` service on localhost port `8893`. The web dashboard proxies to the same runtime at `/api/prospects`. The CLI entry point is:

```bash
python3 -m jarvis business-scan "US-19 Thomaston Georgia" --max-results 10 --generate 1
```

Known public directory sources can be supplied with repeated `--source-url` arguments or `AEGIS_PROSPECT_SOURCE_URLS`. This is useful for municipal and chamber directories that are not discoverable after a search provider quota is exhausted.

## Evidence and uncertainty

Each record stores discovery sources, evidence observations, location class, website state, audit observations, score reasons, research history, and generated asset metadata. Corridor claims are limited to `DIRECTLY_ON_TARGET` when the address contains a target corridor term. Locality matches without corridor evidence are `NEARBY`; incomplete evidence remains `UNKNOWN`.

Website states are `CONFIRMED`, `LIKELY`, `NOT_FOUND`, or `UNKNOWN`. A failed or rate-limited search cannot produce `NOT_FOUND`. Firecrawl MCP errors and fallback transport are preserved in the scan result.

## Website demonstrations

Generated pages are private concept assets, not official business sites. They use verified public name, category, address, and phone fields only; omit unverified services, pricing, reviews, awards, and guarantees; and display a clear non-official demonstration banner. Generation is path-contained and followed by static file, HTML, local preview, and asset checks.

Static preview verification is implemented. Browser visual verification is reported as unavailable when Playwright/Chromium or a connected browser surface is not installed; the system does not claim visual completion in that state. Outreach, publishing as the business, domain purchases, spending, contracts, and production deployment are not autonomous actions in this capability and require separate authorization.

## Research transports

The shared Firecrawl adapter uses the official admitted MCP path first. When that path is unavailable or rate-limited, the prospecting workflow attempts bounded direct HTTP search/scraping. A fallback that returns no evidence produces an explicit degraded scan and preserves `UNKNOWN` rather than manufacturing a conclusion.
