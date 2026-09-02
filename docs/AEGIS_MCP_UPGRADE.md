# AEGIS MCP Capability Fabric

## Research conclusion

`punkpeye/awesome-mcp-servers` is a discovery catalog, not a dependency to copy into AEGIS. The current catalog spans browser automation, biology, cloud, code execution, coding agents, databases, data science, logistics/delivery, developer tools, finance, file systems, gaming, memory, legal, real estate, research, security, social media, travel, version control, and other integrations.

AEGIS therefore treats every catalog entry as a potential capability provider, while keeping a single internal execution contract. A server is never trusted merely because it appears in the catalog.

## Research-derived upgrades

### 1. Universal protocol fabric

AEGIS now owns a dependency-free MCP client for stdio and Streamable HTTP. The transport layer handles JSON-RPC requests, tool discovery, pagination, and tool calls. This is aligned with the current MCP transport model; Streamable HTTP is the current replacement for the older HTTP+SSE transport. See the MCP transport specification.

### 2. Progressive capability disclosure

Large MCP inventories create schema/context bloat. AEGIS exposes a searchable capability surface and only resolves the selected tool schema before invocation. This internalizes the strongest idea observed in unified aggregators and context-firewall-style systems without adopting their runtime as a dependency.

### 3. Admission before execution

MCP servers cross a trust boundary. AEGIS performs a local admission inspection before a server becomes callable, detects dangerous capability classes, tracks permissions, and supports pluggable security scanners. External scanner failures are fail-closed.

This is designed to accept a future SkillSpector adapter without coupling the core to one scanner.

### 4. Evidence-backed trust

The MCP Queen research model is useful as an architectural pattern: reachability/protocol/tooling/latency/provenance should be evidence, not a popularity score. AEGIS records admission and invocation events through the existing evidence sink.

### 5. Unified runtime, not duplicated clients

The 1MCP pattern demonstrates the value of one runtime in front of many upstream servers, presets, filtering, and lazy loading. AEGIS implements those responsibilities natively so its orchestrator remains provider-neutral.

### 6. Context efficiency

The context-firewall research demonstrates that both tool-definition bloat and giant tool outputs are first-class scaling problems. AEGIS's next extension point is a result-budget store with handles for oversized outputs; the present fabric already prevents unnecessary tool schemas from entering the model context until a tool is selected.

## Capability-family mapping

The parser maps catalog categories into AEGIS tags. Examples:

- Browser Automation -> browser, automation
- Databases -> database, data
- Delivery -> delivery, logistics
- Finance & Fintech -> finance, fintech
- Knowledge & Memory -> knowledge, memory, retrieval
- Real Estate -> real_estate, property
- Research -> research, evidence
- Search & Data Extraction -> search, extraction
- Security -> security, compliance
- Version Control -> git, software_engineering
- Workplace & Productivity -> productivity, workflow

This gives the planner a stable vocabulary even as the third-party catalog changes.

## Integration boundary

```text
Catalog / server.json / operator config
                 |
                 v
        AEGIS MCP Catalog Parser
                 |
                 v
        Capability Normalization
                 |
                 v
          Security Admission
                 |
          +------+------+
          |             |
       reject        approve
                        |
                        v
              Progressive Discovery
                        |
                        v
                 Tool Selection
                        |
                        v
                    Policy
                        |
                        v
                    Execute
                        |
                        v
              Evidence + Verification
```

## Important safety rule

MCP descriptions, schemas, URLs, and tool outputs are untrusted data. They may contain instructions that look authoritative. The language model must never treat tool metadata as a higher-priority instruction than AEGIS policy, and no server gets write or command capabilities simply because its metadata claims they are safe.

## Sources researched

- MCP transport specification and 2026-07-28 protocol changes.
- `punkpeye/awesome-mcp-servers` current catalog.
- 1MCP unified runtime.
- MCP Queen evidence/grading layer.
- Context Firewall progressive disclosure/output compression.
- Microsoft Playwright MCP structured accessibility-tree browser automation.
- Upstash Context7 version-aware documentation retrieval.
- Official MCP examples for filesystem, GitHub, memory, and related reference servers.
