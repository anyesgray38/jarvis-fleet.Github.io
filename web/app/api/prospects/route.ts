import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const upstream = (process.env.AEGIS_PROSPECT_URL || 'http://127.0.0.1:8893').replace(/\/$/, '')
const token = process.env.AEGIS_PROSPECT_TOKEN

async function request(path: string, init?: RequestInit) {
  if (!token) return { ok: false, status: 503, data: { ok: false, error: 'Prospecting runtime is not configured' } }
  try {
    const response = await fetch(`${upstream}${path}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(125000),
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...(init?.headers || {}) },
    })
    const data = await response.json().catch(() => ({}))
    return { ok: response.ok, status: response.status, data }
  } catch (error) {
    return { ok: false, status: 503, data: { ok: false, error: error instanceof Error ? error.message : 'Prospecting runtime unavailable' } }
  }
}

export async function GET(req: Request) {
  const url = new URL(req.url)
  const path = url.searchParams.has('businesses') ? `/businesses?${url.searchParams.toString()}` : '/scans'
  const result = await request(path)
  return NextResponse.json(result.data, { status: result.ok ? 200 : result.status })
}

export async function POST(req: Request) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }
  const action = typeof body.action === 'string' ? body.action : 'scan'
  const path = action === 'scan' ? '/scan' : typeof body.business_id === 'string' && action === 'research' ? `/business/${encodeURIComponent(body.business_id)}/research` : typeof body.business_id === 'string' && action === 'demo' ? `/business/${encodeURIComponent(body.business_id)}/demo` : ''
  if (!path) return NextResponse.json({ ok: false, error: 'unsupported prospecting action' }, { status: 400 })
  const result = await request(path, { method: 'POST', body: JSON.stringify(body) })
  return NextResponse.json(result.data, { status: result.ok ? 200 : result.status })
}
