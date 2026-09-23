'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import AegisChat from './AegisChat'

type Summary = {
  total_bookings: number
  upcoming_bookings: number
  completed_bookings: number
  booked_revenue_cents: number
  realized_revenue_cents: number
  pipeline_revenue_cents: number
  month_booked_revenue_cents: number
}
type Appointment = { id: string; starts_at: string; status: string; service_name: string; price_cents: number; customer_name: string; email: string; phone: string | null; notes: string | null }
type SharkData = { ok: boolean; configured: boolean; connected: boolean; error: string | null; metrics: { summary: Summary; services: { service_name: string; bookings: number; revenue_cents: number }[]; security: { admin_auth: boolean; database_configured: boolean; cors_restricted: boolean } } | null; appointments: Appointment[]; fetchedAt: string }

const initial: SharkData = { ok: false, configured: false, connected: false, error: null, metrics: null, appointments: [], fetchedAt: '' }

const money = (cents: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format((cents || 0) / 100)
const dateTime = (value: string) => new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })

export default function SharkDashboard() {
  const [data, setData] = useState<SharkData>(initial)
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/shark', { cache: 'no-store' })
      const next = await response.json()
      setData(next)
    } catch {
      setData({ ...initial, error: 'Shark API proxy unavailable' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 30000)
    return () => clearInterval(id)
  }, [refresh])

  async function updateStatus(id: string, status: string) {
    setAction(id)
    try {
      const response = await fetch('/api/shark', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, status }) })
      if (!response.ok) throw new Error('Unable to update appointment')
      await refresh()
    } catch (error) {
      setData(current => ({ ...current, error: error instanceof Error ? error.message : 'Unable to update appointment' }))
    } finally {
      setAction(null)
    }
  }

  const summary = data.metrics?.summary
  const context = useMemo(() => summary ? `You are assisting the Shark After Dark operator. This is a private grooming studio. Current verified dashboard snapshot: ${summary.upcoming_bookings} upcoming bookings, ${summary.completed_bookings} completed bookings, ${money(summary.month_booked_revenue_cents)} booked this month, ${money(summary.pipeline_revenue_cents)} in future booking pipeline, and ${data.appointments.length} appointment records loaded. Do not invent financial, customer, or security facts; distinguish recommendations from actions. The Aegis dashboard can review and update appointment status through governed server-side controls, but never claim an action completed unless the dashboard confirms it.` : 'You are assisting the Shark After Dark operator. The business dashboard is not connected yet. Explain what data is needed before making operational claims.', [data.appointments.length, summary])

  return <section className="shark-layout">
    <div className="card wide shark-hero"><div><div className="eyebrow">SHARK AFTER DARK · BUSINESS OPS</div><h2>Run the studio through AEGIS.</h2><p className="muted large">Bookings, revenue, security posture, and governed operator assistance in one private workspace.</p></div><div className={`health-state ${data.connected ? 'healthy' : 'offline'}`}><i className={data.connected ? 'dot' : 'dot off'} />{data.connected ? 'CONNECTED' : 'OFFLINE'}</div></div>

    {!data.connected && <div className="notice wide">{data.error || (loading ? 'Connecting to the Shark API…' : 'Set SHARK_API_URL and SHARK_ADMIN_KEY on the Aegis web service to enable Shark Ops.')}</div>}

    <div className="card"><div className="muted">BOOKED THIS MONTH</div><div className="metric">{summary ? money(summary.month_booked_revenue_cents) : '—'}</div><div className="muted">confirmed + completed</div></div>
    <div className="card"><div className="muted">FUTURE PIPELINE</div><div className="metric">{summary ? money(summary.pipeline_revenue_cents) : '—'}</div><div className="muted">pending + confirmed</div></div>
    <div className="card"><div className="muted">UPCOMING</div><div className="metric">{summary ? String(summary.upcoming_bookings).padStart(2, '0') : '—'}</div><div className="muted">active appointments</div></div>
    <div className="card"><div className="muted">REALIZED REVENUE</div><div className="metric">{summary ? money(summary.realized_revenue_cents) : '—'}</div><div className="muted">completed services</div></div>

    <div className="card wide"><div className="eyebrow">BOOKING PIPELINE</div><div className="shark-list">{data.appointments.filter(appointment => ['pending', 'confirmed'].includes(appointment.status)).slice(0, 8).map(appointment => <AppointmentRow key={appointment.id} appointment={appointment} busy={action === appointment.id} onStatus={updateStatus} />)}{!data.appointments.filter(appointment => ['pending', 'confirmed'].includes(appointment.status)).length && <div className="empty">No upcoming appointments loaded.</div>}</div></div>

    <div className="card"><div className="eyebrow">SECURITY POSTURE</div><div className="row"><span>Admin authentication</span><span className="badge">{data.metrics?.security.admin_auth ? 'ENFORCED' : 'CHECK'}</span></div><div className="row"><span>Database connection</span><span className="badge">{data.metrics?.security.database_configured ? 'CONFIGURED' : 'CHECK'}</span></div><div className="row"><span>CORS restriction</span><span className="badge">{data.metrics?.security.cors_restricted ? 'SCOPED' : 'CHECK'}</span></div><div className="muted shark-note">Aegis stores the admin key server-side; it is never sent to browser JavaScript.</div></div>

    <div className="card"><div className="eyebrow">SERVICE MIX</div>{data.metrics?.services.length ? data.metrics.services.map(service => <div className="row" key={service.service_name}><span>{service.service_name}<br /><small className="muted">{service.bookings} bookings</small></span><span>{money(service.revenue_cents)}</span></div>) : <div className="empty">No service data loaded.</div>}</div>

    <div className="card"><div className="eyebrow">SITE + REPO</div><div className="row"><span>Public site</span><a className="shark-link" href="https://anyesgray38.github.io/shark-after-dark/" target="_blank" rel="noreferrer">OPEN ↗</a></div><div className="row"><span>Source repository</span><a className="shark-link" href="https://github.com/anyesgray38/shark-after-dark" target="_blank" rel="noreferrer">GITHUB ↗</a></div><div className="row"><span>Public frontend</span><span className="badge">PAGES</span></div><div className="row"><span>Booking API</span><span className="badge">RENDER</span></div></div>

    <div className="wide"><AegisChat initialPurpose="planning" title="Shark operating assistant" subtitle="Aegis reasons over the verified business snapshot and stays local-only." context={context} /></div>

    <div className="card wide"><div className="eyebrow">OPERATING BOUNDARY</div><p className="muted large">Aegis may analyze the dashboard snapshot, identify trends, draft operational plans, and update appointment status through the authenticated proxy. Payments, refunds, customer messaging, and destructive actions remain explicit future capabilities with their own approvals and audit trails.</p></div>
  </section>
}

function AppointmentRow({ appointment, busy, onStatus }: { appointment: Appointment; busy: boolean; onStatus: (id: string, status: string) => void }) {
  return <div className="shark-appointment"><div><strong>{appointment.customer_name}</strong><div className="muted">{appointment.service_name} · {dateTime(appointment.starts_at)} · {money(appointment.price_cents)}</div><div className="muted">{appointment.email}{appointment.phone ? ` · ${appointment.phone}` : ''}</div></div><select value={appointment.status} onChange={event => onStatus(appointment.id, event.target.value)} disabled={busy} aria-label={`Update ${appointment.customer_name} appointment status`}><option value="pending">Pending</option><option value="confirmed">Confirmed</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option><option value="no_show">No-show</option></select></div>
}
