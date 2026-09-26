'use client'

import { useMemo, useState } from 'react'

type Agent = {
  id: number
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

type Props = {
  agents: Agent[]
  jobs: Job[]
  connected: boolean
  onNavigate: (section: string) => void
  onAction: (payload: Record<string, unknown>) => Promise<void>
}

type AgentCard = {
  key: string
  label: string
  subtitle: string
  color: string
  target: string
  icon: string
}

const agentCards: AgentCard[] = [
  { key: 'research', label: 'RESEARCH AGENT', subtitle: 'Data · Trends · Opportunities', color: 'cyan', target: 'Aegis Floor', icon: '◎' },
  { key: 'business', label: 'BUSINESS AGENT', subtitle: 'Prospecting · Growth · Scaling', color: 'green', target: 'Prospecting', icon: '◈' },
  { key: 'content', label: 'CONTENT AGENT', subtitle: 'Create · Schedule · Engage', color: 'pink', target: 'Agents', icon: '✦' },
  { key: 'web', label: 'WEB & APP AGENT', subtitle: 'Build · Deploy · Optimize', color: 'violet', target: 'Tasks', icon: '⌘' },
  { key: 'trading', label: 'TRADING AGENT', subtitle: 'Markets · Strategies · Execution', color: 'amber', target: 'Tasks', icon: '↗' },
  { key: 'realestate', label: 'REAL ESTATE AGENT', subtitle: 'Deals · Comps · Analysis', color: 'orange', target: 'Prospecting', icon: '⌂' },
  { key: 'logistics', label: 'LOGISTICS AGENT', subtitle: 'Routes · Fleet · Operations', color: 'blue', target: 'Tasks', icon: '▣' },
  { key: 'finance', label: 'FINANCE & TAX AGENT', subtitle: 'Books · Taxes · Planning', color: 'teal', target: 'Overview', icon: '$' },
]

const timeModes = [
  { key: 'past', label: 'PAST', detail: 'LEARN · TRACE · VERIFY' },
  { key: 'present', label: 'PRESENT', detail: 'OBSERVE · EXECUTE · RECORD' },
  { key: 'future', label: 'FUTURE', detail: 'PLAN · TEST · BUILD' },
]

export default function AegisCommandCenter({ agents, jobs, connected, onNavigate, onAction }: Props) {
  const [mode, setMode] = useState('present')
  const [selected, setSelected] = useState<string | null>(null)
  const liveAgents = agents.filter(agent => agent.alive).length
  const activeJobs = jobs.filter(job => ['running', 'queued'].includes(job.status)).length
  const selectedAgent = agentCards.find(agent => agent.key === selected)

  const activity = useMemo(() => jobs.slice().reverse().slice(0, 7), [jobs])

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
          <span><strong>{agent.label}</strong><small>{agent.subtitle}</small><em>{agents.length ? (agents[index % Math.max(agents.length, 1)]?.alive ? '● ONLINE' : '○ STANDBY') : '○ AWAITING NODE'}</em></span>
        </button>)}

        <button type="button" className="aegis-brain" onClick={() => onNavigate('Overview')} aria-label="Open AEGIS main control brain">
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
          <button type="button" onClick={() => onNavigate('Maintenance')}><b>◌ SELF-HEALING</b><span>Monitor · Validate · Repair</span></button>
          <button type="button" onClick={() => onNavigate('Maintenance')}><b>◇ GOVERNANCE LOOP</b><span>Observe · Verify · Record</span></button>
          <button type="button" onClick={() => onNavigate('Tasks')}><b>⌘ SYSTEM BUILDER</b><span>Design · Build · Test · Deploy</span></button>
        </div>

        {selectedAgent && <div className="aegis-agent-detail" role="dialog" aria-label={selectedAgent.label}>
          <div>
            <span className={`aegis-detail-icon tone-${selectedAgent.color}`}>{selectedAgent.icon}</span>
            <div><div className="aegis-kicker">{selectedAgent.label}</div><strong>{selectedAgent.subtitle}</strong></div>
          </div>
          <div className="aegis-detail-actions">
            <button type="button" onClick={() => onNavigate(selectedAgent.target)}>OPEN WORKSPACE</button>
            <button type="button" className="secondary" onClick={() => void onAction({ action: 'queue', hostname: agents.find(agent => agent.alive)?.hostname || agents[0]?.hostname || '', cmd: `AEGIS agent intent: inspect ${selectedAgent.key} workspace` })} disabled={!agents.length}>DISPATCH THROUGH AEGIS</button>
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

    <div className="aegis-bottom-grid">
      <AegisInsight title="LIVE COLLABORATION" icon="◉" copy="The network is represented as a connected graph; live counts come from the control plane." action="View Network" onClick={() => onNavigate('Agents')} />
      <AegisInsight title="NEW SYSTEMS" icon="▦" copy="System Builder routes real work into the existing task and maintenance surfaces instead of inventing telemetry." action="Open Builder" onClick={() => onNavigate('Tasks')} />
      <AegisInsight title="OPPORTUNITY DETECTION" icon="⌖" copy="Prospecting is connected to the evidence-backed knowledge runtime and website-gap workflow." action="View Opportunities" onClick={() => onNavigate('Prospecting')} />
      <AegisInsight title="PERFORMANCE" icon="↗" copy="Performance surfaces remain tied to returned jobs and agent state; no synthetic percentages are shown." action="View Metrics" onClick={() => onNavigate('Overview')} />
      <div className="aegis-activity">
        <div className="aegis-panel-title">SYSTEM ACTIVITY</div>
        <div className="aegis-activity-live"><i className={connected ? 'dot' : 'dot off'} />{connected ? 'Live' : 'Offline'}</div>
        {activity.length ? activity.map(job => <div className="aegis-activity-row" key={job.id}><span>#{job.id}</span><strong>{job.hostname}</strong><small>{job.status}</small></div>) : <div className="aegis-empty">No job activity returned by the control plane.</div>}
      </div>
    </div>
  </section>
}

function AegisInsight({ title, icon, copy, action, onClick }: { title: string; icon: string; copy: string; action: string; onClick: () => void }) {
  return <div className="aegis-insight">
    <div className="aegis-insight-icon">{icon}</div>
    <div className="aegis-panel-title">{title}</div>
    <p>{copy}</p>
    <button type="button" onClick={onClick}>{action} →</button>
  </div>
}
