'use client'
import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import PentestConsole from './components/PentestConsole'
import AegisChat from './components/AegisChat'
import PentestChat from './components/PentestChat'
import AegisFloor from './components/AegisFloor'
import AegisCommandCenter from './components/AegisCommandCenter'
import ProspectingDashboard from './components/ProspectingDashboard'
import MaintenancePanel from './components/MaintenancePanel'

const navGroups = [
  { label: 'Command', items: ['4D Central', 'Aegis Floor', 'Overview', 'Chat'] },
  { label: 'Operations', items: ['Tasks', 'Agents', 'Prospecting'] },
  { label: 'Security', items: ['Pentest Chat', 'Pentest', 'Maintenance'] },
]
type Agent = { id: number; hostname: string; os: string; ip: string; alive: boolean; tags: string[] }
type Job = { id: number; hostname: string; cmd: string; status: string; created_at: string; completed_at: string | null; result: unknown }
type State = { connected: boolean; upstreamConfigured: boolean; agents: Agent[]; jobs: Job[]; error: string | null; fetchedAt: string }
const initial: State = { connected: false, upstreamConfigured: false, agents: [], jobs: [], error: null, fetchedAt: '' }

export default function Home() {
  const [active, setActive] = useState('4D Central')
  const [data, setData] = useState(initial)
  const [loading, setLoading] = useState(true)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setRefreshing(true)
    try {
      const r = await fetch('/api/control-plane', { cache: 'no-store', signal })
      const next = await r.json() as State
      if (!signal?.aborted) setData(next)
    } catch (error) {
      if (!signal?.aborted) setData({ ...initial, error: error instanceof Error ? error.message : 'Dashboard API unavailable' })
    } finally {
      if (!signal?.aborted) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh()
    }, 5000)
    return () => {
      controller.abort()
      window.clearInterval(id)
    }
  }, [refresh])
  const activeJobs = data.jobs.filter(j => ['running', 'queued'].includes(j.status)).length
  const liveAgents = data.agents.filter(a => a.alive).length
  const recentJobs = useMemo(() => data.jobs.slice(-8).reverse(), [data.jobs])
  async function action(payload: Record<string, unknown>) {
    setActionMessage(null)
    try {
      const r = await fetch('/api/control-plane', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await r.json()
      if (!r.ok || !d.ok) throw new Error(d.error || 'Action failed')
      setActionMessage('Action accepted by AEGIS')
      await refresh()
    } catch (e) {
      setActionMessage(e instanceof Error ? e.message : 'Action failed')
    }
  }
  return <div className="shell"><aside className="sidebar"><div className="brand"><div className="brand-mark">A</div><div><div className="brand-name">AEGIS</div><div className="brand-caption">CONTROL CENTER</div></div></div><div className="sidebar-intro">Your governed operator workspace.</div><nav className="nav" aria-label="AEGIS sections">{navGroups.map(group => <div className="nav-group" key={group.label}><div className="nav-label">{group.label}</div>{group.items.map(n => <button type="button" key={n} className={active === n ? 'active' : ''} aria-current={active === n ? 'page' : undefined} onClick={() => { setActive(n); setActionMessage(null) }}><span>{n}</span>{active === n && <span className="nav-current" aria-hidden="true">›</span>}</button>)}</div>)}</nav><div className="sidebar-bottom"><div className="sidebar-status"><i className={data.connected ? 'dot' : 'dot off'} />{data.connected ? 'Systems connected' : 'Gateway offline'}</div><div className="footer">CONTROL PLANE v1.1<br />Private Tailscale workspace</div></div></aside><main className="main"><header className="top"><div><div className="eyebrow">{active} <span className="crumb">/ AEGIS workspace</span></div><div className="title">AEGIS Control Center</div><div className="muted">A clear view of your systems, operations, and next actions.</div></div><div className="status" role="status" aria-live="polite"><i className={data.connected ? 'dot' : 'dot off'} /><span>{data.connected ? 'Systems connected' : 'Gateway disconnected'}</span><button type="button" className="refresh" onClick={() => void refresh()} disabled={refreshing}>{refreshing ? 'Syncing…' : 'Refresh'}</button></div></header>{!data.connected && <div className="notice" role="alert">{data.error || 'Connect the dashboard to the authenticated AEGIS gateway on the Linux host.'}</div>}{actionMessage && <div className={actionMessage.includes('accepted') ? 'notice success' : 'notice'}>{actionMessage}</div>}
      {active === '4D Central' && <AegisCommandCenter agents={data.agents} jobs={data.jobs} connected={data.connected} onNavigate={setActive} onAction={action} />}\n      {active === 'Aegis Floor' && <AegisFloor />}
      {active === 'Prospecting' && <ProspectingDashboard />}
      {active === 'Overview' && <Overview data={data} activeJobs={activeJobs} liveAgents={liveAgents} recentJobs={recentJobs} loading={loading} />}
      {active === 'Chat' && <AegisChat />}
      {active === 'Tasks' && <Tasks agents={data.agents} jobs={data.jobs} onAction={action} />}
      {active === 'Agents' && <Agents agents={data.agents} onAction={action} />}
      {active === 'Pentest Chat' && <PentestChat />}{active === 'Pentest' && <PentestConsole />}{active === 'Maintenance' && <MaintenancePanel />}
      <div className="footer">AEGIS · Live control-plane telemetry · MCP governed · Local model preferred · Tailscale-only access</div></main></div>
}
function Overview({ data, activeJobs, liveAgents, recentJobs, loading }: { data: State; activeJobs: number; liveAgents: number; recentJobs: Job[]; loading: boolean }) {
  return <section className="grid">
    <div className="card">
      <div className="muted">ACTIVE TASKS</div>
      <div className="metric">{activeJobs}</div>
      <div className="muted">live orchestrator jobs</div>
    </div>
    <div className="card">
      <div className="muted">FLEET NODES</div>
      <div className="metric">{liveAgents}</div>
      <div className="muted">agents reporting alive</div>
    </div>
    <div className="card">
      <div className="muted">JOBS RECORDED</div>
      <div className="metric">{data.jobs.length}</div>
      <div className="muted">returned by the control plane</div>
    </div>
    <div className="card">
      <div className="muted">LAST SYNC</div>
      <div className="metric small">{data.fetchedAt ? new Date(data.fetchedAt).toLocaleTimeString() : loading ? '…' : '—'}</div>
      <div className="muted">control-plane response time</div>
    </div>
    <div className="card wide">
      <div className="eyebrow">LIVE TASK GRAPH</div>
      <div style={{ marginTop: 12 }}>{recentJobs.length ? recentJobs.map(j => <JobRow key={j.id} job={j} />) : <div className="empty">No orchestrator jobs returned.</div>}</div>
    </div>
    <div className="card wide">
      <div className="eyebrow">LIVE FLEET</div>
      <div className="fleet" style={{ marginTop: 12 }}>{data.agents.length ? data.agents.map(a => <AgentRow key={a.id} agent={a} />) : <div className="empty">No agents returned.</div>}</div>
    </div>
  </section>
}
function Metric({ label, value, note, small }: { label: string; value: string; note: string; small?: boolean }) { return <div className="card"><div className="muted">{label}</div><div className={small ? 'metric small' : 'metric'}>{value}</div><div className="muted">{note}</div></div> }
function Tasks({ agents, jobs, onAction }: { agents: Agent[]; jobs: Job[]; onAction: (p: Record<string, unknown>) => Promise<void> }) { const [hostname, setHostname] = useState(agents[0]?.hostname || ''); const [cmd, setCmd] = useState('uname -a'); const [busy, setBusy] = useState(false); useEffect(() => { if (!hostname && agents[0]) setHostname(agents[0].hostname); if (hostname && !agents.some(a => a.hostname === hostname)) setHostname(agents[0]?.hostname || ''); }, [agents, hostname]); const submit = async (e: FormEvent) => { e.preventDefault(); setBusy(true); await onAction({ action: 'queue', hostname, cmd }); setBusy(false) }; return <section className="grid"><div className="card wide"><div className="eyebrow">Dispatch task</div><h2>Queue an operator task</h2><p className="muted">Routes the task through the local orchestrator. Keep this control plane on the Tailscale network.</p><form className="form" onSubmit={submit} aria-busy={busy}><label>Target node<select value={hostname} onChange={e => setHostname(e.target.value)} disabled={!agents.length || busy} aria-label="Target node">{agents.length ? agents.map(a => <option key={a.id} value={a.hostname}>{a.hostname}</option>) : <option value="">No agents connected</option>}</select></label><label>Command<input value={cmd} onChange={e => setCmd(e.target.value)} maxLength={4000} /></label><button type="submit" className="primary" disabled={!hostname || !cmd.trim() || busy}>{busy ? 'Dispatching…' : 'Dispatch task'}</button></form></div><div className="card wide"><div className="eyebrow">Queue</div>{jobs.length ? jobs.slice().reverse().map(j => <JobRow key={j.id} job={j} />) : <div className="empty">No tasks recorded.</div>}</div></section> }
function Agents({ agents, onAction }: { agents: Agent[]; onAction: (p: Record<string, unknown>) => Promise<void> }) { const [tag, setTag] = useState('worker'); return <section className="grid"><div className="card wide"><div className="eyebrow">Fleet registry</div>{agents.length ? agents.map(a => <div className="agent-control" key={a.id}><AgentRow agent={a} /><div className="inline-form"><input value={tag} onChange={e => setTag(e.target.value)} placeholder="tag" maxLength={32} /><button type="button" onClick={() => onAction({ action: 'tag', agent_id: a.id, tags: Array.from(new Set([...a.tags, tag.trim()])) })} disabled={!tag.trim()}>Add tag</button></div></div>) : <div className="empty">No agents connected.</div>}</div><div className="card"><div className="eyebrow">Admission</div><div className="row"><span>Identity</span><span className="badge">REQUIRED</span></div><div className="row"><span>Attestation</span><span className="badge">REQUIRED</span></div><div className="row"><span>Network</span><span className="badge">TAILSCALE</span></div></div></section> }
function AgentRow({ agent }: { agent: Agent }) { return <div className="node"><div><strong>{agent.hostname}</strong><br /><span>{agent.os} · {agent.ip}{agent.tags.length ? ` · ${agent.tags.join(', ')}` : ''}</span></div><i className={agent.alive ? 'dot' : 'dot off'} /></div> }
function JobRow({ job }: { job: Job }) { return <div className="row"><div><strong>Job #{job.id} · {job.hostname}</strong><div className="muted">{job.cmd}</div></div><span className="badge">{job.status.toUpperCase()}</span></div> }
