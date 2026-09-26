'use client'

import { useCallback, useEffect, useState } from 'react'

type CheckStatus = 'PASS' | 'FAIL' | 'WARN'
type AuditCheck = {
  id: string
  name: string
  owner: string
  status: CheckStatus
  detail: string
  evidence: string
  duration_ms: number
}
type AuditReport = {
  run_id: string
  started_at: string
  completed_at: string
  status: 'PASS' | 'DEGRADED' | 'FAIL'
  summary: { passed: number; failed: number; warnings: number; checks: number }
  checks: AuditCheck[]
  recommendations: { id: string; title: string; owner: string; priority: 'HIGH' | 'MEDIUM'; reason: string }[]
}

function statusClass(status: CheckStatus) {
  return status === 'PASS' ? 'pass' : status === 'WARN' ? 'warn' : 'fail'
}

export default function MaintenancePanel() {
  const [report, setReport] = useState<AuditReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runAudit = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const response = await fetch('/api/audit', { method: 'POST', cache: 'no-store' })
      const data = await response.json() as { report?: AuditReport; error?: string }
      if (!data.report) throw new Error(data.error || 'Maintenance audit did not return a report')
      setReport(data.report)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Maintenance audit unavailable')
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    void runAudit()
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') void runAudit()
    }, 300000)
    return () => window.clearInterval(id)
  }, [runAudit])

  const badge = report
    ? report.status === 'PASS'
      ? 'ALL LIVE CHECKS PASS'
      : report.status === 'DEGRADED'
        ? 'LIVE CHECKS NEED ATTENTION'
        : 'LIVE CHECKS FAILED'
    : 'WAITING FOR LIVE CHECK'

  return <section className="maintenance-page">
    <div className="maintenance-head">
      <div>
        <div className="eyebrow">SYSTEM MAINTENANCE</div>
        <h1>One maintenance surface. Live evidence only.</h1>
        <p className="muted large">Every signal below comes from the current audit request. No seeded counts, fake uptime, simulated workers, or placeholder health values are displayed.</p>
      </div>
      <div className={`maintenance-badge audit-${report?.status?.toLowerCase() || 'none'}`}><i className="dot" /> {badge}</div>
    </div>

    <div className="audit-toolbar">
      <span className="muted">{report ? `Run ${report.run_id} · completed ${new Date(report.completed_at).toLocaleString()}` : 'No completed live audit.'}</span>
      <button type="button" className="intake-button secondary" onClick={() => void runAudit()} disabled={busy}>{busy ? 'Checking live systems…' : 'Run live maintenance check'}</button>
    </div>

    {error && <div className="notice" role="alert">{error}</div>}

    {report && <div className="maintenance-summary">
      <div><span>Passed</span><strong>{report.summary.passed}</strong></div>
      <div><span>Warnings</span><strong>{report.summary.warnings}</strong></div>
      <div><span>Failed</span><strong>{report.summary.failed}</strong></div>
      <div><span>Signals checked</span><strong>{report.summary.checks}</strong></div>
    </div>}

    <div className="maintenance-signals">
      {report?.checks.map(check => <article className="maintenance-signal" key={check.id}>
        <div className={`audit-status ${statusClass(check.status)}`}>{check.status}</div>
        <div className="maintenance-signal-copy">
          <div className="maintenance-signal-top">
            <div>
              <div className="eyebrow">{check.owner}</div>
              <h2>{check.name}</h2>
            </div>
            <span className="muted">{check.duration_ms} ms</span>
          </div>
          <p>{check.detail}</p>
          <small>{check.evidence}</small>
        </div>
      </article>)}
    </div>

    {!report && !error && <div className="empty">Running the live maintenance check…</div>}

    {report && <section className="maintenance-recommendations">
      <div className="eyebrow">EVIDENCE-BASED ACTIONS</div>
      {report.recommendations.length
        ? report.recommendations.map(item => <div className="recommendation" key={item.id}>
            <div className="recommendation-mark">{item.priority === 'HIGH' ? '!' : '↗'}</div>
            <div className="recommendation-content"><strong>{item.title}</strong><span>{item.owner} · {item.reason}</span></div>
          </div>)
        : <div className="audit-clear">No action was generated from this live audit.</div>}
    </section>}
  </section>
}
