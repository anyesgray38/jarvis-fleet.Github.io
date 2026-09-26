'use client'

import { useCallback, useEffect, useState } from 'react'
import type { AgentSiteConfig } from '../../lib/agent-sites'

type Node = { id: number; designated_name: string; hostname: string; os: string; ip: string; alive: boolean; tags: string[] }
type Job = { id: number; hostname: string; cmd: string; status: string; created_at: string; completed_at: string | null; result: unknown }
type SourceState = { departments?: { id: string; name: string; manager: string; packets: number; status: string; search_command?: string; capabilities?: string[] }[]; research?: { due_departments?: string[]; cycles?: { completed_at: string; packets: number; pipeline?: { fetch: number; reverse_engineer: number; verify: number; compact: number; promote: number } }[] }; businesses?: Record<string, unknown>[]; items?: { name: string; kind: string; files: string[]; updated_at: string; url: string }[]; error?: string | null }
type SiteState = { connected: boolean; nodes: Node[]; jobs: Job[]; sources: { knowledge?: SourceState; prospects?: SourceState; previews?: SourceState }; fetchedAt: string; error: string | null }

export default function AgentSiteDashboard({ site }: { site: AgentSiteConfig }) {
  const [state, setState] = useState<SiteState>({ connected: false, nodes: [], jobs: [], sources: {}, fetchedAt: '', error: null })
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`/api/agents/${site.key}`, { cache: 'no-store' })
      const next = await response.json() as SiteState
      setState(next)
    } catch (error) {
      setState(current => ({ ...current, error: error instanceof Error ? error.message : 'agent site unavailable' }))
    }
  }, [site.key])

  useEffect(() => {
    void refresh()
    const interval = window.setInterval(() => { if (document.visibilityState === 'visible') void refresh() }, 5000)
    return () => window.clearInterval(interval)
  }, [refresh])

  async function runTest(testId: string) {
    if (busy) return
    setBusy(testId); setMessage(null)
    try {
      const response = await fetch(`/api/agents/${site.key}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ test_id: testId }) })
      const result = await response.json()
      if (!response.ok || !result.ok) throw new Error(result.error || 'agent test failed')
      setMessage(`${result.test} queued on ${result.hostname}`)
      await refresh()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'agent test failed')
    } finally { setBusy(null) }
  }

  const liveNodes = state.nodes.filter(node => node.alive).length
  const knowledge = state.sources.knowledge
  const prospects = state.sources.prospects
  const previews = state.sources.previews

  return <div className="agent-site" style={{ '--agent-accent': site.accent } as React.CSSProperties}>
    <header className="agent-site-top"><a className="agent-site-back" href="/">← 4D CENTRAL</a><div className="agent-site-status"><i className={state.connected && liveNodes ? 'dot' : 'dot off'} />{state.connected && liveNodes ? 'LIVE AGENT SITE' : 'AGENT STANDBY'}</div></header>
    <main className="agent-site-main">
      <section className="agent-site-hero"><div><div className="agent-site-kicker">AEGIS PERSONAL CONTROL SYSTEM · {site.key.toUpperCase()}</div><h1>{site.siteTitle}</h1><p>{site.mission}</p></div><div className="agent-site-identity"><span>{site.label}</span><strong>{liveNodes}/{state.nodes.length} live nodes</strong><small>{state.fetchedAt ? `synced ${new Date(state.fetchedAt).toLocaleTimeString()}` : 'syncing'}</small></div></section>

      {state.error && <div className="agent-site-notice">{state.error}</div>}
      {message && <div className="agent-site-notice success">{message}</div>}

      <section className="agent-site-grid agent-site-overview">
        <div className="agent-site-card agent-site-command"><div className="agent-site-label">DESIGNATED SEARCH COMMAND</div><strong>{site.searchCommand}</strong><span>Only this site’s configured sources are pulled into this agent view.</span></div>
        {site.metrics.map(metric => <div className="agent-site-card" key={metric.label}><div className="agent-site-label">{metric.label}</div><strong>{metric.value}</strong></div>)}
        <div className="agent-site-card"><div className="agent-site-label">ASSIGNED WORKERS</div><strong>{state.nodes.length}</strong><span>{state.nodes.map(node => node.designated_name || node.hostname).join(' · ') || 'No assigned worker'}</span></div>
      </section>

      <section className="agent-site-layout"><div className="agent-site-card agent-site-test-bay"><div className="agent-site-section-head"><div><div className="agent-site-label">{site.label} TEST BAY</div><h2>Run this agent alone</h2></div><span>{site.tests.length} registered tests</span></div>{site.tests.map(test => <button type="button" className="agent-site-test" key={test.id} onClick={() => void runTest(test.id)} disabled={Boolean(busy) || !liveNodes}><span><strong>{test.label}</strong><small>{test.detail}</small></span><i>{busy === test.id ? 'QUEUING…' : 'RUN ↗'}</i></button>)}</div><div className="agent-site-card agent-site-options"><div className="agent-site-label">ROLE OPTIONS</div>{site.options.map(option => <div className="agent-site-option" key={option.label}><span>{option.label}</span><strong>{option.value}</strong></div>)}</div></section>

      {site.key === 'research' && <ResearchPanel knowledge={knowledge} />}
      {site.key === 'business' && <BusinessPanel prospects={prospects} />}
      {site.key === 'web' && <BuilderPanel previews={previews} />}
      {!['research', 'business', 'web'].includes(site.key) && <OperationalPanel site={site} nodes={state.nodes} />}

      <section className="agent-site-card agent-site-jobs"><div className="agent-site-section-head"><div><div className="agent-site-label">SCOPED ACTIVITY</div><h2>This agent only</h2></div><span>{state.jobs.length} jobs returned</span></div>{state.jobs.length ? state.jobs.slice().reverse().slice(0, 10).map(job => <div className="agent-site-job" key={job.id}><span>#{job.id}</span><strong>{job.cmd}</strong><small>{job.status}</small></div>) : <div className="agent-site-empty">No activity for this agent yet.</div>}</section>
    </main>
  </div>
}

function ResearchPanel({ knowledge }: { knowledge?: SourceState }) {
  const departments = knowledge?.departments || []
  const latest = knowledge?.research?.cycles?.[0]
  return <section className="agent-site-card agent-site-data"><div className="agent-site-section-head"><div><div className="agent-site-label">ATLAS KNOWLEDGE INTAKE</div><h2>Research stations</h2></div><span>{knowledge?.research?.due_departments?.length || 0} due</span></div><div className="agent-site-data-grid">{departments.map(department => <div key={department.id}><strong>{department.name}</strong><span>{department.packets} packets · {department.status}</span><small>{department.search_command || 'No search command'}</small></div>)}</div>{latest?.pipeline && <p className="agent-site-pipeline">Last loop: fetch {latest.pipeline.fetch} → reverse-engineer {latest.pipeline.reverse_engineer} → verify {latest.pipeline.verify} → compact {latest.pipeline.compact} → promote {latest.pipeline.promote}</p>}</section>
}

function BusinessPanel({ prospects }: { prospects?: SourceState }) {
  return <section className="agent-site-card agent-site-data"><div className="agent-site-section-head"><div><div className="agent-site-label">HARBOR PROSPECTING</div><h2>Stored opportunities</h2></div><span>{prospects?.businesses?.length || 0} loaded</span></div>{prospects?.businesses?.length ? <div className="agent-site-data-grid">{prospects.businesses.map((business, index) => <div key={String(business.business_id || business.id || index)}><strong>{String(business.business_name || business.name || 'Unnamed business')}</strong><span>{String(business.classification || business.category || 'classification pending')}</span><small>score {String(business.opportunity_score ?? '—')}</small></div>)}</div> : <div className="agent-site-empty">No prospect records are available to this site.</div>}</section>
}

function BuilderPanel({ previews }: { previews?: SourceState }) {
  return <section className="agent-site-card agent-site-data"><div className="agent-site-section-head"><div><div className="agent-site-label">FORGE OUTPUT</div><h2>Private generated sites</h2></div><span>{previews?.items?.length || 0} previews</span></div>{previews?.items?.length ? <div className="agent-site-data-grid">{previews.items.map(preview => <a href={preview.url} target="_blank" rel="noreferrer" key={preview.name}><strong>{preview.name}</strong><span>{preview.kind} · {preview.files.length} files</span><small>updated {new Date(preview.updated_at).toLocaleString()}</small></a>)}</div> : <div className="agent-site-empty">No generated previews are available to this site.</div>}</section>
}

function OperationalPanel({ site, nodes }: { site: AgentSiteConfig; nodes: Node[] }) {
  return <section className="agent-site-card agent-site-data"><div className="agent-site-section-head"><div><div className="agent-site-label">{site.label} CONTROL BAY</div><h2>Designated operating scope</h2></div><span>{nodes.length} assigned</span></div><div className="agent-site-data-grid">{site.options.map(option => <div key={option.label}><strong>{option.label}</strong><span>{option.value}</span><small>Approval and verification remain required before external action.</small></div>)}</div></section>
}
