'use client'

import { useEffect, useMemo, useState } from 'react'

type Agent = {
  id: number
  designated_name: string
  hostname: string
  os: string
  ip: string
  alive: boolean
  tags: string[]
}

type Job = {
  id: number
  hostname: string
  cmd: string
  status: string
  created_at: string
  completed_at: string | null
  result: unknown
}

type Preview = {
  name: string
  kind: 'website' | 'app'
  files: string[]
  updated_at: string
  url: string
}

type Props = {
  agents: Agent[]
  jobs: Job[]
  connected: boolean
  onAction: (payload: Record<string, unknown>) => Promise<void>
}

type AgentCard = {
  key: string
  label: string
  subtitle: string
  color: string
  icon: string
}

const agentCards: AgentCard[] = [
  { key: 'research', label: 'RESEARCH AGENT', subtitle: 'Data · Trends · Opportunities', color: 'cyan', icon: '◎' },
  { key: 'business', label: 'BUSINESS AGENT', subtitle: 'Prospecting · Growth · Scaling', color: 'green', icon: '◈' },
  { key: 'content', label: 'CONTENT AGENT', subtitle: 'Create · Schedule · Engage', color: 'pink', icon: '✦' },
  { key: 'web', label: 'WEB & APP AGENT', subtitle: 'Build · Deploy · Optimize', color: 'violet', icon: '⌘' },
  { key: 'trading', label: 'TRADING AGENT', subtitle: 'Markets · Strategies · Execution', color: 'amber', icon: '↗' },
  { key: 'realestate', label: 'REAL ESTATE AGENT', subtitle: 'Deals · Comps · Analysis', color: 'orange', icon: '⌂' },
  { key: 'logistics', label: 'LOGISTICS AGENT', subtitle: 'Routes · Fleet · Operations', color: 'blue', icon: '▣' },
  { key: 'finance', label: 'FINANCE & TAX AGENT', subtitle: 'Books · Taxes · Planning', color: 'teal', icon: '$' },
]

const timeModes = [
  { key: 'past', label: 'PAST', detail: 'LEARN · TRACE · VERIFY' },
  { key: 'present', label: 'PRESENT', detail: 'OBSERVE · EXECUTE · RECORD' },
  { key: 'future', label: 'FUTURE', detail: 'PLAN · TEST · BUILD' },
]

const capabilityTags: Record<string, string> = {
  research: 'research',
  business: 'business-prospecting',
  content: 'content',
  web: 'code-factory',
  trading: 'trading',
  realestate: 'real-estate',
  logistics: 'logistics',
  finance: 'finance',
}

type AgentTest = { label: string; detail: string; command: string }
type AgentProfile = { mission: string; searchCommand: string; metrics: { label: string; value: string }[]; options: { label: string; value: string }[]; tests: AgentTest[] }

const agentProfiles: Record<string, AgentProfile> = {
  research: {
    mission: 'Grow evidence-backed local knowledge without promoting unverified source text.',
    searchCommand: 'current web research and agentic AI operations',
    metrics: [{ label: 'MEMORY LOOP', value: 'Fetch → understand → compact' }, { label: 'EVIDENCE MODE', value: 'Local packets + archive' }],
    options: [{ label: 'INBOUND', value: 'Wikipedia and Firecrawl research' }, { label: 'REVERSE ENGINEER', value: 'Claims · concepts · provenance' }, { label: 'OUTPUT', value: 'Department-scoped knowledge packets' }],
    tests: [
      { label: 'READ DEPARTMENT MEMORY', detail: 'Inspect live search commands, packet counts, and due research stations.', command: 'python3 -m jarvis --json knowledge departments' },
      { label: 'RUN RESEARCH CYCLE', detail: 'Execute the bounded continuous research loop for due departments.', command: 'python3 -m jarvis --json knowledge research --force' },
      { label: 'CHECK LOCAL RECALL', detail: 'Confirm the second brain can retrieve compact local evidence.', command: 'python3 -m jarvis --json knowledge search "agentic web research" --limit 5' },
    ],
  },
  business: {
    mission: 'Find qualified businesses, verify their digital presence, and prepare evidence-backed demos.',
    searchCommand: 'local business digital presence and conversion',
    metrics: [{ label: 'DISCOVERY', value: 'Corridor · radius · category' }, { label: 'OUTPUT', value: 'Prospect + website demo' }],
    options: [{ label: 'DISCOVER', value: 'Business names · addresses · categories' }, { label: 'AUDIT', value: 'Website · social · conversion gaps' }, { label: 'BUILD', value: 'Tailored demo with verified facts' }],
    tests: [
      { label: 'READ PROSPECT INVENTORY', detail: 'Load locally stored businesses and their explainable opportunity scores.', command: 'python3 -m jarvis --json prospect list --min-score 0 --limit 10' },
      { label: 'SCAN THOMASTON SAMPLE', detail: 'Run a bounded real discovery scan against the configured prospecting workflow.', command: 'python3 -m jarvis --json business-scan "Downtown Thomaston GA" --max-results 5' },
      { label: 'CHECK PROSPECT WORKSPACE', detail: 'Inspect the evidence workspace used for stored prospect records.', command: 'python3 -m jarvis --json inspect .jarvis' },
    ],
  },
  content: {
    mission: 'Prepare content work for review while preserving approval boundaries before publishing.',
    searchCommand: 'content planning, brand voice, and audience research',
    metrics: [{ label: 'WORKFLOW', value: 'Plan → draft → review' }, { label: 'PUBLISHING', value: 'Approval required' }],
    options: [{ label: 'PLAN', value: 'Audience · voice · campaign intent' }, { label: 'CREATE', value: 'Drafts and reusable content blocks' }, { label: 'REVIEW', value: 'Evidence and approval gate before send' }],
    tests: [
      { label: 'CHECK CONTENT CAPABILITY', detail: 'Confirm the node reports the capabilities available to this workspace.', command: 'python3 -m jarvis --json capabilities' },
      { label: 'AUDIT CONTENT WORKSPACE', detail: 'Compile-check the designated content workspace without publishing anything.', command: 'python3 -m jarvis --json audit content' },
      { label: 'INSPECT CONTENT INPUTS', detail: 'Inspect the local content workspace and return contained file evidence.', command: 'python3 -m jarvis --json inspect content' },
    ],
  },
  web: {
    mission: 'Turn a user request into a responsive, functional, tested website or app preview.',
    searchCommand: 'current Next.js production deployment guidance',
    metrics: [{ label: 'PIPELINE', value: 'Design → build → test' }, { label: 'FUNCTIONS', value: 'Forms · booking · apps' }],
    options: [{ label: 'DESIGN', value: 'Brief · layout · allow-listed features' }, { label: 'BUILD', value: 'Website and installable app artifacts' }, { label: 'VERIFY', value: 'Static checks · preview · evidence' }],
    tests: [
      { label: 'RUN WEBSITE BUILDER TEST', detail: 'Generate and verify a functional contact + FAQ website preview.', command: 'python3 -m jarvis --json builder agent-web-test --kind website --title "Agent Web Test" --description "A functional website builder verification artifact." --feature contact_form --feature faq --workspace .jarvis/builds --overwrite' },
      { label: 'RUN APP BUILDER TEST', detail: 'Generate and verify a local task app with a calculator function.', command: 'python3 -m jarvis --json builder agent-app-test --kind app --title "Agent App Test" --description "A functional app builder verification artifact." --feature task_list --feature calculator --workspace .jarvis/builds --overwrite' },
      { label: 'OPEN BUILDER PREVIEW CATALOG', detail: 'Inspect generated artifacts available to the private dashboard preview.', command: 'python3 -m jarvis --json inspect .jarvis/builds' },
    ],
  },
  trading: {
    mission: 'Research market structure and paper-test ideas without placing live orders.',
    searchCommand: 'market structure, strategy research, and paper execution',
    metrics: [{ label: 'EXECUTION', value: 'Paper only' }, { label: 'RISK GATE', value: 'Research before action' }],
    options: [{ label: 'RESEARCH', value: 'Universe · regime · strategy hypotheses' }, { label: 'TEST', value: 'Deterministic backtests and paper broker' }, { label: 'BOUNDARY', value: 'No live order placement' }],
    tests: [
      { label: 'AUDIT TRADING MODULE', detail: 'Compile-check trading research and paper execution code.', command: 'python3 -m jarvis --json audit trading' },
      { label: 'INSPECT MARKET CONFIG', detail: 'Read the configured research-first trading universe and boundaries.', command: 'python3 -m jarvis --json inspect trading/markets.json' },
      { label: 'CHECK PAPER EXECUTION FILES', detail: 'Inspect the paper broker and research modules without placing orders.', command: 'python3 -m jarvis --json inspect trading' },
    ],
  },
  realestate: {
    mission: 'Normalize property research into comparable, evidence-backed deal analysis.',
    searchCommand: 'property research, comparable sales, and deal analysis',
    metrics: [{ label: 'METHOD', value: 'Normalize → compare' }, { label: 'OUTPUT', value: 'Evidence-backed analysis' }],
    options: [{ label: 'COLLECT', value: 'Listings · addresses · property facts' }, { label: 'NORMALIZE', value: 'Canonical property identity and fields' }, { label: 'REPORT', value: 'Comparables and uncertainty notes' }],
    tests: [
      { label: 'CHECK REAL ESTATE CAPABILITY', detail: 'Confirm the node’s registered capabilities before assigning property work.', command: 'python3 -m jarvis --json capabilities' },
      { label: 'AUDIT PROPERTY MODULE', detail: 'Compile-check the designated real-estate workspace.', command: 'python3 -m jarvis --json audit realestate' },
      { label: 'INSPECT DEAL INPUTS', detail: 'Inspect local property research inputs without making claims about a property.', command: 'python3 -m jarvis --json inspect realestate' },
    ],
  },
  logistics: {
    mission: 'Coordinate routes, fleet state, and operational evidence for distribution work.',
    searchCommand: 'route planning, fleet operations, and logistics optimization',
    metrics: [{ label: 'FLOW', value: 'Inbound → route → outbound' }, { label: 'CONTROL', value: 'Validate before dispatch' }],
    options: [{ label: 'INBOUND', value: 'Orders · stops · constraints' }, { label: 'PLAN', value: 'Routes · fleet · worker assignments' }, { label: 'OUTBOUND', value: 'Dispatch-ready operational plan' }],
    tests: [
      { label: 'AUDIT ROUTING MODULE', detail: 'Compile-check the logistics planning workspace.', command: 'python3 -m jarvis --json audit logistics' },
      { label: 'INSPECT FLEET CONFIG', detail: 'Read contained fleet configuration and node assignments.', command: 'python3 -m jarvis --json inspect fleet' },
      { label: 'CHECK ROUTE INPUTS', detail: 'Inspect logistics inputs without dispatching an external shipment.', command: 'python3 -m jarvis --json inspect logistics' },
    ],
  },
  finance: {
    mission: 'Organize financial and tax planning inputs with review and approval boundaries.',
    searchCommand: 'bookkeeping, tax planning, and financial operations',
    metrics: [{ label: 'FLOW', value: 'Collect → reconcile → report' }, { label: 'BOUNDARY', value: 'Review before filing' }],
    options: [{ label: 'COLLECT', value: 'Transactions · receipts · account inputs' }, { label: 'RECONCILE', value: 'Normalize and identify exceptions' }, { label: 'REPORT', value: 'Planning output for human review' }],
    tests: [
      { label: 'CHECK FINANCE CAPABILITY', detail: 'Confirm which governed capabilities are available to this node.', command: 'python3 -m jarvis --json capabilities' },
      { label: 'AUDIT FINANCE WORKSPACE', detail: 'Compile-check the finance workspace without filing or sending anything.', command: 'python3 -m jarvis --json audit finance' },
      { label: 'INSPECT ACCOUNTING INPUTS', detail: 'Inspect contained finance inputs before any reconciliation task.', command: 'python3 -m jarvis --json inspect finance' },
    ],
  },
}

function capabilityState(key: string, agents: Agent[]) {
  const tag = capabilityTags[key]
  const assigned = agents.filter(agent => agent.tags.includes(tag))
  if (!assigned.length) return '○ NO ASSIGNED NODE'
  return assigned.some(agent => agent.alive) ? '● READY VIA NODE' : '○ NODE STANDBY'
}

export default function AegisCommandCenter({ agents, jobs, connected, onAction }: Props) {
  const [mode, setMode] = useState('present')
  const [selected, setSelected] = useState<string | null>(null)
  const [previews, setPreviews] = useState<Preview[]>([])
  const [selectedPreview, setSelectedPreview] = useState<string | null>(null)
  const liveAgents = agents.filter(agent => agent.alive).length
  const activeJobs = jobs.filter(job => ['running', 'queued'].includes(job.status)).length
  const selectedAgent = agentCards.find(agent => agent.key === selected)
  const selectedProfile = selectedAgent ? agentProfiles[selectedAgent.key] : null

  const activity = useMemo(() => jobs.slice().reverse().slice(0, 7), [jobs])

  useEffect(() => {
    let cancelled = false
    const refreshPreviews = async () => {
      try {
        const response = await fetch('/api/previews', { cache: 'no-store' })
        const payload = await response.json() as { previews?: Preview[] }
        if (cancelled) return
        const next = Array.isArray(payload.previews) ? payload.previews : []
        setPreviews(next)
        setSelectedPreview(current => current && next.some(preview => preview.name === current) ? current : next[0]?.name || null)
      } catch {
        if (!cancelled) setPreviews([])
      }
    }
    void refreshPreviews()
    const interval = window.setInterval(() => void refreshPreviews(), 5000)
    return () => { cancelled = true; window.clearInterval(interval) }
  }, [])

  function openAgent(agent: AgentCard) {
    setSelected(agent.key)
  }

  return <section className="aegis-4d">
    <div className="aegis-4d-topline">
      <div>
        <div className="aegis-kicker">AEGIS · 4D COMMAND INTERFACE</div>
        <h1>One control brain. A living agent network.</h1>
        <p>Click any agent in the 4D field to open its connected workspace. The visualization reflects live control-plane state instead of fabricated telemetry.</p>
      </div>
      <div className="aegis-live-pill"><i className={connected ? 'dot' : 'dot off'} />{connected ? 'LIVE CONTROL PLANE' : 'GATEWAY OFFLINE'}</div>
    </div>

    <div className="aegis-4d-layout">
      <aside className="aegis-interface-panel">
        <div className="aegis-panel-title">4D INTERFACE</div>
        <div className="aegis-panel-sub">CONTROL · EXPLORE · BUILD · EVOLVE</div>
        <div className="aegis-4d-orbit" aria-label="4D navigation">
          <div className="aegis-orbit-ring ring-a" />
          <div className="aegis-orbit-ring ring-b" />
          <div className="aegis-orbit-ring ring-c" />
          <button type="button" className="aegis-dimension-core" onClick={() => setMode('present')}>
            <span>4D</span><small>SPACE + TIME</small>
          </button>
          {timeModes.map((item, index) => <button key={item.key} type="button" className={`aegis-mode-node mode-${index + 1} ${mode === item.key ? 'selected' : ''}`} onClick={() => setMode(item.key)}>
            <b>{item.label}</b><small>{item.detail}</small>
          </button>)}
        </div>
        <div className="aegis-dimension-note">
          <span>ACTIVE DIMENSION</span>
          <strong>{timeModes.find(item => item.key === mode)?.label}</strong>
          <small>Time is treated as a navigation layer over the same connected agent graph.</small>
        </div>
        <div className="aegis-mini-network">
          <div className="aegis-panel-title">AGENT NETWORK</div>
          <div className="aegis-network-lines">
            {agentCards.slice(0, 6).map((agent, index) => <button type="button" key={agent.key} className={`aegis-network-node n${index + 1}`} onClick={() => openAgent(agent)} aria-label={`Open ${agent.label}`}>
              {agent.icon}
            </button>)}
          </div>
          <div className="aegis-live-stat"><span>LIVE CONNECTIONS</span><strong>{connected ? liveAgents : 0}/{agents.length || 0}</strong></div>
          <div className="aegis-live-stat"><span>ACTIVE TASKS</span><strong>{activeJobs}</strong></div>
          <div className="aegis-live-stat"><span>SYSTEM STATE</span><strong>{connected ? 'LIVE' : 'OFFLINE'}</strong></div>
        </div>
      </aside>

      <div className="aegis-command-stage">
        <div className="aegis-stage-grid" aria-hidden="true" />
        <div className="aegis-energy energy-one" aria-hidden="true" />
        <div className="aegis-energy energy-two" aria-hidden="true" />

        {agentCards.map((agent, index) => <button type="button" key={agent.key} className={`aegis-agent agent-${index + 1} tone-${agent.color} ${selected === agent.key ? 'is-selected' : ''}`} onClick={() => openAgent(agent)}>
          <span className="aegis-agent-icon">{agent.icon}</span>
          <span><strong>{agent.label}</strong><small>{agent.subtitle}</small><em>{capabilityState(agent.key, agents)}</em></span>
        </button>)}

        <button type="button" className="aegis-brain" onClick={() => setSelected(null)} aria-label="Keep AEGIS main control brain in focus">
          <span className="brain-halo" />
          <span className="brain-orbit orbit-1" />
          <span className="brain-orbit orbit-2" />
          <span className="brain-core-mark">A</span>
          <strong>AEGIS</strong>
          <small>MASTER CONTROL</small>
          <span className="brain-line">ORCHESTRATE · ANALYZE · EXECUTE</span>
          <span className="brain-clock">24/7 CONTROL LOOP</span>
        </button>

        <div className="aegis-control-cards">
          <div><b>◌ SELF-HEALING</b><span>Monitor · Validate · Repair</span></div>
          <div><b>◇ GOVERNANCE LOOP</b><span>Observe · Verify · Record</span></div>
          <div><b>⌘ SYSTEM BUILDER</b><span>Design · Build · Test · Deploy</span></div>
        </div>

        {selectedAgent && <div className="aegis-agent-detail" role="dialog" aria-label={selectedAgent.label}>
          <div>
            <span className={`aegis-detail-icon tone-${selectedAgent.color}`}>{selectedAgent.icon}</span>
            <div><div className="aegis-kicker">{selectedAgent.label}</div><strong>{selectedAgent.subtitle}</strong></div>
          </div>
          <div className="aegis-detail-actions">
            <a className="agent-site-open" href={`/agents/${selectedAgent.key}`}>OPEN {selectedAgent.label} SITE ↗</a>
            <button type="button" className="secondary" onClick={() => { const node = agents.find(agent => agent.tags.includes(capabilityTags[selectedAgent.key]) && agent.alive) || agents.find(agent => agent.tags.includes(capabilityTags[selectedAgent.key])) || agents.find(agent => agent.alive) || agents[0]; if (node && selectedProfile) void onAction({ action: 'queue', hostname: node.hostname, cmd: selectedProfile.tests[0].command }) }} disabled={!agents.length || !selectedProfile}>RUN {selectedProfile?.tests[0].label || 'AGENT TEST'}</button>
            <button type="button" className="close" onClick={() => setSelected(null)} aria-label="Close agent detail">×</button>
          </div>
        </div>}

        <div className="aegis-center-caption">
          <span>MAIN CONTROL BRAIN</span>
          <strong>Connected agents exchange work through the governed control plane.</strong>
          <small>New system ideas can be routed into the existing task, maintenance, knowledge, and prospecting workspaces.</small>
        </div>
      </div>

      <aside className="aegis-sync-panel">
        <div className="aegis-panel-title">LIVE SYSTEM SYNC</div>
        <div className="aegis-sync-item"><i className="sync-cyan" />Agents communicating</div>
        <div className="aegis-sync-item"><i className="sync-green" />Sharing data & insights</div>
        <div className="aegis-sync-item"><i className="sync-amber" />Building new systems</div>
        <div className="aegis-sync-item"><i className="sync-pink" />Scanning opportunities</div>
        <div className="aegis-sync-item"><i className="sync-violet" />Optimizing performance</div>
        <div className="aegis-sync-wave" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /></div>
        <div className="aegis-sync-note">{connected ? 'Live endpoint connected. Visual activity is driven by returned fleet/job state.' : 'Connect the gateway to replace standby visualization with live fleet state.'}</div>
      </aside>
    </div>

    {selectedAgent ? <AgentWorkspace agent={selectedAgent} agents={agents} jobs={jobs} connected={connected} onAction={onAction} onClose={() => setSelected(null)} /> : <>
      <DemoPreviewPanel previews={previews} selected={selectedPreview} onSelect={setSelectedPreview} />

      <div className="aegis-bottom-grid">
      <AegisInsight title="LIVE COLLABORATION" icon="◉" copy="The network is represented as a connected graph; live counts come from the control plane." status="CENTRAL VIEW" />
      <AegisInsight title="NEW SYSTEMS" icon="▦" copy="System Builder routes real work through AEGIS while this central surface keeps the command chain visible." status="CENTRAL VIEW" />
      <AegisInsight title="OPPORTUNITY DETECTION" icon="⌖" copy="Prospecting remains connected to the evidence-backed knowledge runtime and website-gap workflow." status="CENTRAL VIEW" />
      <AegisInsight title="PERFORMANCE" icon="↗" copy="Performance is tied to returned jobs and agent state; no synthetic percentages are shown." status="CENTRAL VIEW" />
      <div className="aegis-roster">
        <div className="aegis-panel-title">DESIGNATED AGENTS</div>
        {agents.length ? agents.map(agent => <div className="aegis-roster-row" key={agent.id}><span className={agent.alive ? 'dot' : 'dot off'} /><div><strong>{agent.designated_name || agent.hostname}</strong><small>{agent.hostname} · {agent.tags.length ? agent.tags.join(', ') : 'unassigned'}</small></div></div>) : <div className="aegis-empty">No agents connected.</div>}
      </div>
      <div className="aegis-activity">
        <div className="aegis-panel-title">SYSTEM ACTIVITY</div>
        <div className="aegis-activity-live"><i className={connected ? 'dot' : 'dot off'} />{connected ? 'Live' : 'Offline'}</div>
        {activity.length ? activity.map(job => <div className="aegis-activity-row" key={job.id}><span>#{job.id}</span><strong>{job.hostname}</strong><small>{job.status}</small></div>) : <div className="aegis-empty">No job activity returned by the control plane.</div>}
      </div>
      </div>
    </>}
  </section>
}

function AgentWorkspace({ agent, agents, jobs, connected, onAction, onClose }: { agent: AgentCard; agents: Agent[]; jobs: Job[]; connected: boolean; onAction: (payload: Record<string, unknown>) => Promise<void>; onClose: () => void }) {
  const tag = capabilityTags[agent.key]
  const profile = agentProfiles[agent.key]
  const assigned = agents.filter(node => node.tags.includes(tag))
  const activeNode = assigned.find(node => node.alive) || assigned[0] || agents.find(node => node.alive) || agents[0]
  const roleJobs = jobs.filter(job => assigned.some(node => node.hostname === job.hostname))

  function dispatch(test: AgentTest) {
    if (!activeNode) return
    void onAction({ action: 'queue', hostname: activeNode.hostname, cmd: test.command })
  }

  return <section className="aegis-agent-workspace" aria-label={`${agent.label} dashboard`}>
    <div className="aegis-workspace-header">
      <div className="aegis-workspace-identity">
        <span className={`aegis-workspace-icon tone-${agent.color}`}>{agent.icon}</span>
        <div><div className="aegis-kicker">INDIVIDUAL AGENT WORKSPACE</div><h2>{agent.label}</h2><p>{profile.mission}</p></div>
      </div>
      <div className="aegis-workspace-actions"><span className={connected && assigned.some(node => node.alive) ? 'aegis-workspace-status online' : 'aegis-workspace-status'}>{connected && assigned.some(node => node.alive) ? 'LIVE NODE READY' : 'NODE NOT READY'}</span><button type="button" className="close" onClick={onClose}>BACK TO CENTRAL</button></div>
    </div>

    <div className="aegis-workspace-grid">
      <div className="aegis-workspace-card aegis-workspace-overview"><div className="aegis-panel-title">AGENT OVERVIEW</div><div className="aegis-workspace-metric"><span>DESIGNATED ROLE</span><strong>{agent.key.toUpperCase()}</strong></div><div className="aegis-workspace-metric"><span>ASSIGNED NODES</span><strong>{assigned.length}</strong></div><div className="aegis-workspace-metric"><span>LIVE NODES</span><strong>{assigned.filter(node => node.alive).length}</strong></div><div className="aegis-workspace-metric"><span>CAPABILITY TAG</span><strong>{tag}</strong></div>{profile.metrics.map(metric => <div className="aegis-workspace-metric" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong></div>)}<div className="aegis-workspace-nodes">{assigned.length ? assigned.map(node => <div key={node.id}><i className={node.alive ? 'dot' : 'dot off'} /><span><strong>{node.designated_name || node.hostname}</strong><small>{node.hostname} · {node.os}</small></span></div>) : <div className="aegis-empty">No node is assigned this role yet.</div>}</div></div>

      <div className="aegis-workspace-card aegis-workspace-tests"><div className="aegis-panel-title">{agent.label} TEST BAY</div><p className="aegis-workspace-copy">These checks are defined for this role and run against its selected node.</p>{profile.tests.map(test => <button type="button" key={test.label} className="aegis-test-option" onClick={() => dispatch(test)} disabled={!activeNode}><span><strong>{test.label}</strong><small>{test.detail}</small></span><i>RUN ↗</i></button>)}</div>

      <div className="aegis-workspace-card aegis-workspace-capabilities"><div className="aegis-panel-title">{agent.label} OPTIONS</div><div className="aegis-role-options">{profile.options.map(option => <div key={option.label}><span>{option.label}</span><strong>{option.value}</strong></div>)}</div><div className="aegis-workspace-route"><span>DESIGNATED SEARCH COMMAND</span><strong>{profile.searchCommand}</strong></div><div className="aegis-workspace-route"><span>CONTROL ROUTE</span><strong>{tag} → AEGIS → {activeNode?.hostname || 'unassigned'}</strong></div></div>

      <div className="aegis-workspace-card aegis-workspace-activity"><div className="aegis-panel-title">THIS AGENT’S ACTIVITY</div>{roleJobs.length ? roleJobs.slice().reverse().slice(0, 8).map(job => <div className="aegis-activity-row" key={job.id}><span>#{job.id}</span><strong>{job.cmd.slice(0, 42)}</strong><small>{job.status}</small></div>) : <div className="aegis-empty">No recent jobs for this agent. Run an individual test above.</div>}</div>
    </div>
  </section>
}

function AegisInsight({ title, icon, copy, status }: { title: string; icon: string; copy: string; status: string }) {
  return <div className="aegis-insight">
    <div className="aegis-insight-icon">{icon}</div>
    <div className="aegis-panel-title">{title}</div>
    <p>{copy}</p>
    <span className="aegis-insight-status">{status}</span>
  </div>
}

function DemoPreviewPanel({ previews, selected, onSelect }: { previews: Preview[]; selected: string | null; onSelect: (name: string) => void }) {
  const active = previews.find(preview => preview.name === selected) || previews[0]
  return <section className="aegis-preview-panel" aria-label="Generated demo previews">
    <div className="aegis-preview-heading">
      <div><div className="aegis-kicker">AEGIS · BUILDER OUTPUT</div><h2>DEMO WEBSITE PREVIEW</h2><p>Open the actual artifact created by the autonomous builder. Previews remain private and read-only until deployment is separately authorized.</p></div>
      <span className="aegis-preview-count">{previews.length} ARTIFACT{previews.length === 1 ? '' : 'S'}</span>
    </div>
    {active ? <div className="aegis-preview-layout">
      <div className="aegis-preview-list">
        {previews.map(preview => <button type="button" key={preview.name} className={preview.name === active.name ? 'selected' : ''} onClick={() => onSelect(preview.name)}><span><strong>{preview.name}</strong><small>{preview.kind.toUpperCase()} · {preview.files.length} files</small></span><i>›</i></button>)}
      </div>
      <div className="aegis-preview-frame-wrap">
        <div className="aegis-preview-toolbar"><span className="dot" /> <strong>{active.name}</strong><a href={active.url} target="_blank" rel="noreferrer">OPEN FULL DEMO ↗</a></div>
        <iframe className="aegis-preview-frame" src={active.url} title={`${active.name} generated demo`} sandbox="allow-scripts allow-forms" />
      </div>
    </div> : <div className="aegis-empty aegis-preview-empty">No generated demos yet. Run the autonomous builder to create the first preview.</div>}
  </section>
}
