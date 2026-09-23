import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const upstream = (process.env.SHARK_API_URL || 'https://shark-after-dark.onrender.com').replace(/\/$/, '')
const adminKey = process.env.SHARK_ADMIN_KEY
type ProxyResult = { ok: boolean; data?: Record<string, any>; error?: string }

async function request(path: string, init?: RequestInit): Promise<ProxyResult> {
  if (!upstream || !adminKey) return { ok: false, error: 'Shark API integration is not configured' }
  try {
    const response = await fetch(`${upstream}${path}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': adminKey, ...(init?.headers || {}) },
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) return { ok: false, error: data?.error || `Shark API returned ${response.status}` }
    return { ok: true, data }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'Shark API unavailable' }
  }
}

export async function GET() {
  const [health, metrics, appointments] = await Promise.all([
    upstream ? request('/health') : Promise.resolve<ProxyResult>({ ok: false, error: 'SHARK_API_URL is not configured' }),
    request('/api/admin/metrics'),
    request('/api/appointments'),
  ])

  return NextResponse.json({
    ok: health.ok && metrics.ok && appointments.ok,
    configured: Boolean(upstream && adminKey),
    connected: health.ok && metrics.ok,
    health: health.ok ? health.data : null,
    metrics: metrics.ok ? metrics.data : null,
    appointments: appointments.ok && Array.isArray(appointments.data?.appointments) ? appointments.data.appointments : [],
    error: health.error || metrics.error || appointments.error || null,
    fetchedAt: new Date().toISOString(),
  })
}

export async function PATCH(req: Request) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }

  const id = typeof body.id === 'string' ? body.id.trim() : ''
  const status = typeof body.status === 'string' ? body.status.trim() : ''
  if (!id || !status) return NextResponse.json({ ok: false, error: 'id and status are required' }, { status: 400 })
  if (!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({ ok: false, error: 'invalid appointment id' }, { status: 400 })

  const result = await request(`/api/appointments/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
  return NextResponse.json(result, { status: result.ok ? 200 : 502 })
}
