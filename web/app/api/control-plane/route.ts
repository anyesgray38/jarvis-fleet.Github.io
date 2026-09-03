import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const upstream = process.env.AEGIS_ORCHESTRATOR_URL?.replace(/\/$/, '')

async function request(path: string, init?: RequestInit) {
  if (!upstream) return { ok: false, error: 'AEGIS_ORCHESTRATOR_URL is not configured' }
  try {
    const response = await fetch(`${upstream}${path}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) return { ok: false, error: data?.error || `upstream returned ${response.status}` }
    return { ok: true, data }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'upstream unavailable' }
  }
}

async function get(path: string) {
  return request(path)
}

export async function GET() {
  const [health, agents, jobs] = await Promise.all([
    get('/health'),
    get('/agents'),
    get('/jobs'),
  ])

  const agentList = agents.ok && Array.isArray(agents.data?.agents) ? agents.data.agents : []
  const jobList = jobs.ok && Array.isArray(jobs.data?.jobs) ? jobs.data.jobs : []

  return NextResponse.json({
    connected: Boolean(upstream) && health.ok,
    upstreamConfigured: Boolean(upstream),
    health: health.ok ? health.data : null,
    agents: agentList,
    jobs: jobList,
    error: health.error || agents.error || jobs.error || null,
    fetchedAt: new Date().toISOString(),
  })
}

export async function POST(req: Request) {
  if (!upstream) return NextResponse.json({ ok: false, error: 'AEGIS_ORCHESTRATOR_URL is not configured' }, { status: 503 })

  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }

  const action = body.action

  if (action === 'queue') {
    const hostname = typeof body.hostname === 'string' ? body.hostname.trim() : ''
    const cmd = typeof body.cmd === 'string' ? body.cmd.trim() : ''
    if (!hostname || !cmd) return NextResponse.json({ ok: false, error: 'hostname and cmd are required' }, { status: 400 })
    if (hostname.length > 255 || cmd.length > 4000) return NextResponse.json({ ok: false, error: 'input exceeds allowed length' }, { status: 400 })
    const result = await request('/queue', { method: 'POST', body: JSON.stringify({ hostname, cmd }) })
    return NextResponse.json(result, { status: result.ok ? 200 : 502 })
  }

  if (action === 'tag') {
    const agentId = Number(body.agent_id)
    const tags = Array.isArray(body.tags) ? body.tags.filter((tag): tag is string => typeof tag === 'string').map(tag => tag.trim()).filter(Boolean) : []
    if (!Number.isInteger(agentId) || agentId < 1 || tags.length === 0 || tags.length > 20) {
      return NextResponse.json({ ok: false, error: 'valid agent_id and tags are required' }, { status: 400 })
    }
    const result = await request(`/agents/${agentId}/tag`, { method: 'POST', body: JSON.stringify({ tags }) })
    return NextResponse.json(result, { status: result.ok ? 200 : 502 })
  }

  if (action === 'pine') {
    const agentId = Number(body.agent_id)
    const script = typeof body.script === 'string' ? body.script : ''
    const symbol = typeof body.symbol === 'string' ? body.symbol.trim() : ''
    if (!Number.isInteger(agentId) || agentId < 1 || !script.trim() || !symbol) {
      return NextResponse.json({ ok: false, error: 'agent_id, script and symbol are required' }, { status: 400 })
    }
    if (script.length > 20000 || symbol.length > 100) return NextResponse.json({ ok: false, error: 'input exceeds allowed length' }, { status: 400 })
    const result = await request(`/agents/${agentId}/pine`, { method: 'POST', body: JSON.stringify({
      script,
      symbol,
      provider: typeof body.provider === 'string' ? body.provider : undefined,
      timeframe: typeof body.timeframe === 'string' ? body.timeframe : undefined,
      limit: Number.isInteger(body.limit) ? body.limit : undefined,
    }) })
    return NextResponse.json(result, { status: result.ok ? 200 : 502 })
  }

  return NextResponse.json({ ok: false, error: 'unsupported action' }, { status: 400 })
}
