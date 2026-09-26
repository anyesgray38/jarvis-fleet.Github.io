export type AgentTest = { id: string; label: string; detail: string; command: string }
export type AgentSiteConfig = {
  key: string
  label: string
  tag: string
  accent: string
  mission: string
  searchCommand: string
  siteTitle: string
  dataSources: ('control-plane' | 'knowledge' | 'prospects' | 'previews')[]
  departmentIds: string[]
  metrics: { label: string; value: string }[]
  options: { label: string; value: string }[]
  tests: AgentTest[]
}

const profile = (config: Omit<AgentSiteConfig, 'key'> & { key: string }): AgentSiteConfig => config

export const AGENT_SITE_CONFIG: Record<string, AgentSiteConfig> = {
  research: profile({
    key: 'research', label: 'RESEARCH AGENT', tag: 'research', accent: '#68d9ee', siteTitle: 'Atlas Research Station',
    mission: 'Grow evidence-backed local knowledge without promoting unverified source text.', searchCommand: 'current web research and agentic AI operations',
    dataSources: ['control-plane', 'knowledge'], departmentIds: ['web-intelligence', 'security', 'code-factory'],
    metrics: [{ label: 'MEMORY LOOP', value: 'Fetch → understand → compact' }, { label: 'EVIDENCE MODE', value: 'Local packets + archive' }],
    options: [{ label: 'INBOUND', value: 'Wikipedia and Firecrawl research' }, { label: 'REVERSE ENGINEER', value: 'Claims · concepts · provenance' }, { label: 'OUTPUT', value: 'Department-scoped knowledge packets' }],
    tests: [
      { id: 'department-memory', label: 'READ DEPARTMENT MEMORY', detail: 'Inspect live search commands, packet counts, and due research stations.', command: 'python3 -m jarvis --json knowledge departments' },
      { id: 'research-cycle', label: 'RUN RESEARCH CYCLE', detail: 'Execute the bounded continuous research loop for due departments.', command: 'python3 -m jarvis --json knowledge research --force' },
      { id: 'local-recall', label: 'CHECK LOCAL RECALL', detail: 'Confirm the second brain can retrieve compact local evidence.', command: 'python3 -m jarvis --json knowledge search "agentic web research" --limit 5' },
    ],
  }),
  business: profile({
    key: 'business', label: 'BUSINESS AGENT', tag: 'business-prospecting', accent: '#72e8a9', siteTitle: 'Harbor Growth Desk',
    mission: 'Find qualified businesses, verify their digital presence, and prepare evidence-backed demos.', searchCommand: 'local business digital presence and conversion',
    dataSources: ['control-plane', 'prospects'], departmentIds: ['business-prospecting'],
    metrics: [{ label: 'DISCOVERY', value: 'Corridor · radius · category' }, { label: 'OUTPUT', value: 'Prospect + website demo' }],
    options: [{ label: 'DISCOVER', value: 'Business names · addresses · categories' }, { label: 'AUDIT', value: 'Website · social · conversion gaps' }, { label: 'BUILD', value: 'Tailored demo with verified facts' }],
    tests: [
      { id: 'prospect-inventory', label: 'READ PROSPECT INVENTORY', detail: 'Load locally stored businesses and their explainable opportunity scores.', command: 'python3 -m jarvis --json prospect list --min-score 0 --limit 10' },
      { id: 'thomaston-scan', label: 'SCAN THOMASTON SAMPLE', detail: 'Run a bounded real discovery scan against the configured prospecting workflow.', command: 'python3 -m jarvis --json business-scan "Downtown Thomaston GA" --max-results 5' },
      { id: 'prospect-workspace', label: 'CHECK PROSPECT WORKSPACE', detail: 'Inspect the evidence workspace used for stored prospect records.', command: 'python3 -m jarvis --json inspect .jarvis' },
    ],
  }),
  content: profile({
    key: 'content', label: 'CONTENT AGENT', tag: 'content', accent: '#f27bd6', siteTitle: 'Muse Content Studio',
    mission: 'Prepare content work for review while preserving approval boundaries before publishing.', searchCommand: 'content planning, brand voice, and audience research',
    dataSources: ['control-plane'], departmentIds: [],
    metrics: [{ label: 'WORKFLOW', value: 'Plan → draft → review' }, { label: 'PUBLISHING', value: 'Approval required' }],
    options: [{ label: 'PLAN', value: 'Audience · voice · campaign intent' }, { label: 'CREATE', value: 'Drafts and reusable content blocks' }, { label: 'REVIEW', value: 'Evidence and approval gate before send' }],
    tests: [
      { id: 'content-capability', label: 'CHECK CONTENT CAPABILITY', detail: 'Confirm the node reports the capabilities available to this workspace.', command: 'python3 -m jarvis --json capabilities' },
      { id: 'content-audit', label: 'AUDIT CONTENT WORKSPACE', detail: 'Compile-check the designated content workspace without publishing anything.', command: 'python3 -m jarvis --json audit content' },
      { id: 'content-inputs', label: 'INSPECT CONTENT INPUTS', detail: 'Inspect the local content workspace and return contained file evidence.', command: 'python3 -m jarvis --json inspect content' },
    ],
  }),
  web: profile({
    key: 'web', label: 'WEB & APP AGENT', tag: 'code-factory', accent: '#a88cff', siteTitle: 'Forge Web Foundry',
    mission: 'Turn a user request into a responsive, functional, tested website or app preview.', searchCommand: 'current Next.js production deployment guidance',
    dataSources: ['control-plane', 'previews'], departmentIds: ['code-factory'],
    metrics: [{ label: 'PIPELINE', value: 'Design → build → test' }, { label: 'FUNCTIONS', value: 'Forms · booking · apps' }],
    options: [{ label: 'DESIGN', value: 'Brief · layout · allow-listed features' }, { label: 'BUILD', value: 'Website and installable app artifacts' }, { label: 'VERIFY', value: 'Static checks · preview · evidence' }],
    tests: [
      { id: 'website-builder', label: 'RUN WEBSITE BUILDER TEST', detail: 'Generate and verify a functional contact + FAQ website preview.', command: 'python3 -m jarvis --json builder agent-web-test --kind website --title "Agent Web Test" --description "A functional website builder verification artifact." --feature contact_form --feature faq --workspace .jarvis/builds --overwrite' },
      { id: 'app-builder', label: 'RUN APP BUILDER TEST', detail: 'Generate and verify a local task app with a calculator function.', command: 'python3 -m jarvis --json builder agent-app-test --kind app --title "Agent App Test" --description "A functional app builder verification artifact." --feature task_list --feature calculator --workspace .jarvis/builds --overwrite' },
      { id: 'preview-catalog', label: 'OPEN BUILDER PREVIEW CATALOG', detail: 'Inspect generated artifacts available to the private dashboard preview.', command: 'python3 -m jarvis --json inspect .jarvis/builds' },
    ],
  }),
  trading: profile({
    key: 'trading', label: 'TRADING AGENT', tag: 'trading', accent: '#f3c86b', siteTitle: 'Vector Market Lab',
    mission: 'Research market structure and paper-test ideas without placing live orders.', searchCommand: 'market structure, strategy research, and paper execution',
    dataSources: ['control-plane'], departmentIds: [],
    metrics: [{ label: 'EXECUTION', value: 'Paper only' }, { label: 'RISK GATE', value: 'Research before action' }],
    options: [{ label: 'RESEARCH', value: 'Universe · regime · strategy hypotheses' }, { label: 'TEST', value: 'Deterministic backtests and paper broker' }, { label: 'BOUNDARY', value: 'No live order placement' }],
    tests: [
      { id: 'trading-audit', label: 'AUDIT TRADING MODULE', detail: 'Compile-check trading research and paper execution code.', command: 'python3 -m jarvis --json audit trading' },
      { id: 'market-config', label: 'INSPECT MARKET CONFIG', detail: 'Read the configured research-first trading universe and boundaries.', command: 'python3 -m jarvis --json inspect trading/markets.json' },
      { id: 'paper-execution', label: 'CHECK PAPER EXECUTION FILES', detail: 'Inspect the paper broker and research modules without placing orders.', command: 'python3 -m jarvis --json inspect trading' },
    ],
  }),
  realestate: profile({
    key: 'realestate', label: 'REAL ESTATE AGENT', tag: 'real-estate', accent: '#ffab69', siteTitle: 'Parcel Analysis Office',
    mission: 'Normalize property research into comparable, evidence-backed deal analysis.', searchCommand: 'property research, comparable sales, and deal analysis',
    dataSources: ['control-plane'], departmentIds: [],
    metrics: [{ label: 'METHOD', value: 'Normalize → compare' }, { label: 'OUTPUT', value: 'Evidence-backed analysis' }],
    options: [{ label: 'COLLECT', value: 'Listings · addresses · property facts' }, { label: 'NORMALIZE', value: 'Canonical property identity and fields' }, { label: 'REPORT', value: 'Comparables and uncertainty notes' }],
    tests: [
      { id: 'realestate-capability', label: 'CHECK REAL ESTATE CAPABILITY', detail: 'Confirm the node’s registered capabilities before assigning property work.', command: 'python3 -m jarvis --json capabilities' },
      { id: 'realestate-audit', label: 'AUDIT PROPERTY MODULE', detail: 'Compile-check the designated real-estate workspace.', command: 'python3 -m jarvis --json audit realestate' },
      { id: 'deal-inputs', label: 'INSPECT DEAL INPUTS', detail: 'Inspect local property research inputs without making claims about a property.', command: 'python3 -m jarvis --json inspect realestate' },
    ],
  }),
  logistics: profile({
    key: 'logistics', label: 'LOGISTICS AGENT', tag: 'logistics', accent: '#72bfff', siteTitle: 'Shark Distribution Desk',
    mission: 'Coordinate routes, fleet state, and operational evidence for distribution work.', searchCommand: 'route planning, fleet operations, and logistics optimization',
    dataSources: ['control-plane'], departmentIds: [],
    metrics: [{ label: 'FLOW', value: 'Inbound → route → outbound' }, { label: 'CONTROL', value: 'Validate before dispatch' }],
    options: [{ label: 'INBOUND', value: 'Orders · stops · constraints' }, { label: 'PLAN', value: 'Routes · fleet · worker assignments' }, { label: 'OUTBOUND', value: 'Dispatch-ready operational plan' }],
    tests: [
      { id: 'routing-audit', label: 'AUDIT ROUTING MODULE', detail: 'Compile-check the logistics planning workspace.', command: 'python3 -m jarvis --json audit logistics' },
      { id: 'fleet-config', label: 'INSPECT FLEET CONFIG', detail: 'Read contained fleet configuration and node assignments.', command: 'python3 -m jarvis --json inspect fleet' },
      { id: 'route-inputs', label: 'CHECK ROUTE INPUTS', detail: 'Inspect logistics inputs without dispatching an external shipment.', command: 'python3 -m jarvis --json inspect logistics' },
    ],
  }),
  finance: profile({
    key: 'finance', label: 'FINANCE & TAX AGENT', tag: 'finance', accent: '#69e2d4', siteTitle: 'Ledger Control Office',
    mission: 'Organize financial and tax planning inputs with review and approval boundaries.', searchCommand: 'bookkeeping, tax planning, and financial operations',
    dataSources: ['control-plane'], departmentIds: [],
    metrics: [{ label: 'FLOW', value: 'Collect → reconcile → report' }, { label: 'BOUNDARY', value: 'Review before filing' }],
    options: [{ label: 'COLLECT', value: 'Transactions · receipts · account inputs' }, { label: 'RECONCILE', value: 'Normalize and identify exceptions' }, { label: 'REPORT', value: 'Planning output for human review' }],
    tests: [
      { id: 'finance-capability', label: 'CHECK FINANCE CAPABILITY', detail: 'Confirm which governed capabilities are available to this node.', command: 'python3 -m jarvis --json capabilities' },
      { id: 'finance-audit', label: 'AUDIT FINANCE WORKSPACE', detail: 'Compile-check the finance workspace without filing or sending anything.', command: 'python3 -m jarvis --json audit finance' },
      { id: 'accounting-inputs', label: 'INSPECT ACCOUNTING INPUTS', detail: 'Inspect contained finance inputs before any reconciliation task.', command: 'python3 -m jarvis --json inspect finance' },
    ],
  }),
}

export function getAgentSite(key: string): AgentSiteConfig | null {
  return AGENT_SITE_CONFIG[key] || null
}
