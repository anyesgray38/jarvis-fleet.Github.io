'use client'

import { useCallback, useEffect, useState } from 'react'

type KnowledgeSnapshot = {
  configured: boolean
  providers: { wikipedia: boolean; firecrawl: boolean }
  metrics: {
    sources_ingested: number
    packets_ready: number
    full_sources_archived: number
    events_7d: number
    words_archived: number
    active_memory_mode: string
  }
  sources: { id: string; title: string; provider: string; manager: string; summary: string; updated_at: string }[]
  error: string | null
}

const initialKnowledge: KnowledgeSnapshot = {
  configured: false,
  providers: { wikipedia: false, firecrawl: false },
  metrics: { sources_ingested: 0, packets_ready: 0, full_sources_archived: 0, events_7d: 0, words_archived: 0, active_memory_mode: 'unknown' },
  sources: [],
  error: null,
}

export default function AegisFloor() {
  const [knowledge, setKnowledge] = useState(initialKnowledge)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/knowledge', { cache: 'no-store' })
      const next = await response.json() as KnowledgeSnapshot
      if (!response.ok) throw new Error(next.error || 'Knowledge service unavailable')
      setKnowledge(next)
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Knowledge service unavailable')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh()
    }, 30000)
    return () => window.clearInterval(id)
  }, [refresh])

  return <section className="floor-page">
    <div className="floor-intro">
      <div>
        <div className="eyebrow">AEGIS OPERATIONS FLOOR · LIVE VIEW</div>
        <h1>Only live system state belongs here.</h1>
        <p className="floor-lede">The floor is intentionally read-only. It reports what the connected knowledge runtime actually returns and keeps maintenance controls in one dedicated tab.</p>
      </div>
      <div className="floor-live-state">
        <i className={knowledge.error || error ? 'dot off' : 'dot'} />
        <div><strong>{knowledge.error || error ? 'KNOWLEDGE RUNTIME UNAVAILABLE' : knowledge.configured ? 'KNOWLEDGE RUNTIME CONNECTED' : 'KNOWLEDGE RUNTIME NOT CONFIGURED'}</strong><span>Runtime refresh completed from the live endpoint.</span></div>
      </div>
    </div>

    {(error || knowledge.error) && <div className="notice" role="alert">{error || knowledge.error}</div>}

    <section className="live-panel">
      <div className="live-panel-head">
        <div><div className="eyebrow">LIVE KNOWLEDGE STATE</div><h2>Current runtime data</h2></div>
        <button type="button" className="intake-button secondary" onClick={() => void refresh()}>Refresh</button>
      </div>
      <div className="floor-kpis live-kpis">
        <LiveKpi label="Sources ingested" value={knowledge.metrics.sources_ingested} />
        <LiveKpi label="Packets ready" value={knowledge.metrics.packets_ready} />
        <LiveKpi label="Archived sources" value={knowledge.metrics.full_sources_archived} />
        <LiveKpi label="Learning events · 7d" value={knowledge.metrics.events_7d} />
      </div>
      <div className="live-detail-grid">
        <div className="card">
          <div className="eyebrow">PROVIDERS</div>
          <LiveRow label="Wikipedia" value={knowledge.providers.wikipedia ? 'CONNECTED' : 'NOT CONNECTED'} />
          <LiveRow label="Firecrawl" value={knowledge.providers.firecrawl ? 'CONNECTED' : 'NOT CONNECTED'} />
          <LiveRow label="Memory mode" value={knowledge.metrics.active_memory_mode.replaceAll('_', ' ')} />
          <LiveRow label="Words archived" value={knowledge.metrics.words_archived.toLocaleString()} />
        </div>
        <div className="card">
          <div className="eyebrow">RECENT SOURCES</div>
          {knowledge.sources.length
            ? knowledge.sources.slice(0, 5).map(source => <div className="source-row" key={source.id}>
                <div><strong>{source.title}</strong><span>{source.provider} · {source.manager}</span></div>
                <small>{new Date(source.updated_at).toLocaleString()}</small>
              </div>)
            : <div className="empty">No source records returned by the runtime.</div>}
        </div>
      </div>
    </section>

    <KnowledgeIntake snapshot={knowledge} onRefresh={refresh} />
  </section>
}

function LiveKpi({ label, value }: { label: string; value: number }) {
  return <div className="floor-kpi"><span>{label}</span><strong>{value.toLocaleString()}</strong><small>runtime value</small></div>
}

function LiveRow({ label, value }: { label: string; value: string }) {
  return <div className="row"><span>{label}</span><span className="badge">{value.toUpperCase()}</span></div>
}

function KnowledgeIntake({ snapshot, onRefresh }: { snapshot: KnowledgeSnapshot; onRefresh: () => Promise<void> }) {
  const [query, setQuery] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function ingest(kind: 'wiki' | 'web') {
    const value = kind === 'wiki' ? query.trim() : url.trim()
    if (!value || busy) return
    setBusy(true)
    setMessage(null)
    try {
      const response = await fetch('/api/knowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(kind === 'wiki'
          ? { kind, query: value, manager: 'Scribe' }
          : { kind, url: value, manager: 'Atlas' }),
      })
      const data = await response.json() as { ok?: boolean; error?: string }
      if (!response.ok || !data.ok) throw new Error(data.error || 'Intake failed')
      setMessage(kind === 'wiki' ? 'Reference packet added to the runtime.' : 'Web source archived and distilled.')
      if (kind === 'web') setUrl('')
      await onRefresh()
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : 'Intake failed')
    } finally {
      setBusy(false)
    }
  }

  return <section className="knowledge-intake">
    <div className="knowledge-intake-head">
      <div><div className="eyebrow">LIVE INTAKE CONSOLE</div><strong>Operate the connected knowledge runtime</strong></div>
      <span className={snapshot.providers.firecrawl ? 'provider-state ready' : 'provider-state'}>{snapshot.providers.firecrawl ? 'FIRECRAWL READY' : 'WIKI ONLY'}</span>
    </div>
    <label>Wiki search<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Topic or question" disabled={busy} /></label>
    <button type="button" className="intake-button" onClick={() => void ingest('wiki')} disabled={!query.trim() || busy}>{busy ? 'Processing…' : 'Search + distill'}</button>
    <label>Web page<input value={url} onChange={event => setUrl(event.target.value)} placeholder="https://…" disabled={busy || !snapshot.providers.firecrawl} /></label>
    <button type="button" className="intake-button secondary" onClick={() => void ingest('web')} disabled={!url.trim() || busy || !snapshot.providers.firecrawl}>{snapshot.providers.firecrawl ? 'Scrape with Firecrawl' : 'Firecrawl not connected'}</button>
    {message && <p className={message.includes('added') || message.includes('archived') ? 'intake-message success' : 'intake-message'}>{message}</p>}
  </section>
}
