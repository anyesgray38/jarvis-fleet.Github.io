import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const upstream = (process.env.AEGIS_KNOWLEDGE_URL || 'http://127.0.0.1:8892').replace(/\/$/, '')
const token = process.env.AEGIS_KNOWLEDGE_TOKEN

async function request(path: string, init?: RequestInit) {
  if (!token) return { ok: false, error: 'Knowledge service is not configured' }
  try {
    const response = await fetch(`${upstream}${path}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(25000),
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(init?.headers || {}),
      },
    })
    const data = await response.json().catch(() => ({}))
    return { ok: response.ok, status: response.status, data }
  } catch (error) {
    return { ok: false, status: 503, data: { ok: false, error: error instanceof Error ? error.message : 'Knowledge service unavailable' } }
  }
}

export async function GET(req: Request) {
  const url = new URL(req.url)
  const path = url.searchParams.has('q') ? `/search?${url.searchParams.toString()}` : url.searchParams.get('departments') === '1' ? '/departments' : '/snapshot'
  const result = await request(path)
  return NextResponse.json(result.data, { status: result.ok ? 200 : result.status || 503 })
}

export async function POST(req: Request) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }
  const result = await request('/ingest', { method: 'POST', body: JSON.stringify(body) })
  return NextResponse.json(result.data, { status: result.ok ? 200 : result.status || 503 })
}
