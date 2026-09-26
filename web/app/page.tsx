'use client'

import { useCallback, useEffect, useState } from 'react'
import AegisCommandCenter from './components/AegisCommandCenter'

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

type State = {
  connected: boolean
  upstreamConfigured: boolean
  agents: Agent[]
  jobs: Job[]
  error: string | null
  fetchedAt: string
}

const initial: State = {
  connected: false,
  upstreamConfigured: false,
  agents: [],
  jobs: [],
  error: null,
  fetchedAt: '',
}

export default function Home() {
  const [data, setData] = useState(initial)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setRefreshing(true)
    try {
      const response = await fetch('/api/control-plane', { cache: 'no-store', signal })
      const next = await response.json() as State
      if (!signal?.aborted) setData(next)
    } catch (error) {
      if (!signal?.aborted) {
        setData({ ...initial, error: error instanceof Error ? error.message : 'Dashboard API unavailable' })
      }
    } finally {
      if (!signal?.aborted) setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh()
    }, 5000)
    return () => {
      controller.abort()
      window.clearInterval(interval)
    }
  }, [refresh])

  async function action(payload: Record<string, unknown>) {
    setActionMessage(null)
    try {
      const response = await fetch('/api/control-plane', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const result = await response.json()
      if (!response.ok || !result.ok) throw new Error(result.error || 'Action failed')
      setActionMessage('Action accepted by AEGIS')
      await refresh()
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : 'Action failed')
    }
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">A</div><div><div className="brand-name">AEGIS</div><div className="brand-caption">CONTROL CENTER</div></div></div>
      <div className="sidebar-intro">One central command surface for the entire agent network.</div>
      <nav className="nav" aria-label="AEGIS sections">
        <div className="nav-group">
          <div className="nav-label">Command</div>
          <button type="button" className="active" aria-current="page"><span>4D Central</span><span className="nav-current" aria-hidden="true">›</span></button>
        </div>
      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-status"><i className={data.connected ? 'dot' : 'dot off'} />{data.connected ? 'Systems connected' : 'Gateway offline'}</div>
        <div className="footer">CONTROL PLANE v1.1<br />Private Tailscale workspace</div>
      </div>
    </aside>
    <main className="main">
      <header className="top">
        <div><div className="eyebrow">4D Central <span className="crumb">/ AEGIS workspace</span></div><div className="title">AEGIS Control Center</div><div className="muted">One brain, one command surface, every designated agent.</div></div>
        <div className="status" role="status" aria-live="polite"><i className={data.connected ? 'dot' : 'dot off'} /><span>{data.connected ? 'Systems connected' : 'Gateway disconnected'}</span><button type="button" className="refresh" onClick={() => void refresh()} disabled={refreshing}>{refreshing ? 'Syncing…' : 'Refresh'}</button></div>
      </header>
      {!data.connected && <div className="notice" role="alert">{data.error || 'Connect the dashboard to the authenticated AEGIS gateway on the Linux host.'}</div>}
      {actionMessage && <div className={actionMessage.includes('accepted') ? 'notice success' : 'notice'}>{actionMessage}</div>}
      <AegisCommandCenter agents={data.agents} jobs={data.jobs} connected={data.connected} onAction={action} />
      <div className="footer">AEGIS · Live control-plane telemetry · MCP governed · Local model preferred · Tailscale-only access</div>
    </main>
  </div>
}
