import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

/**
 * The remote control interface is the UI/control plane. It never talks directly to the AEGIS
 * orchestrator. The Linux AEGIS host exposes a small authenticated gateway.
 *
 * Required remote-interface env:
 *   AEGIS_GATEWAY_URL=https://<private-gateway>
 *   AEGIS_GATEWAY_TOKEN=<long-random-token>
 *
 * Optional:
 *   AEGIS_DEMO_MODE=true
 */
const gateway = process.env.AEGIS_GATEWAY_URL?.replace(/\/$/, '')
const token = process.env.AEGIS_GATEWAY_TOKEN
const demo = process.env.AEGIS_DEMO_MODE === 'true'

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

let demoJobs: Job[] = []
const demoAgents: Agent[] = [
  {
    id: 1,
    designated_name: 'Aegis Demo Worker',
    hostname: 'aegis-local',
    os: 'demo',
    ip: '127.0.0.1',
    alive: true,
    tags: ['demo', 'control-plane'],
  },
]

async function request(path: string, init?: RequestInit) {
  if (!gateway) return { ok: false, error: 'AEGIS_GATEWAY_URL is not configured' }
  if (!token) return { ok: false, error: 'AEGIS_GATEWAY_TOKEN is not configured' }

  try {
    const response = await fetch(`${gateway}${path}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(8000),
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(init?.headers || {}),
      },
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      return { ok: false, error: data?.error || `gateway returned ${response.status}` }
    }
    return { ok: true, data }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'gateway unavailable' }
  }
}

async function get(path: string) {
  return request(path)
}

function demoState() {
  return {
    connected: true,
    upstreamConfigured: true,
    health: { status: 'ok', mode: 'demo' },
    agents: demoAgents,
    jobs: demoJobs,
    error: null,
    fetchedAt: new Date().toISOString(),
  }
}

export async function GET() {
  if (demo) return NextResponse.json(demoState())

  const [health, agents, jobs] = await Promise.all([
    get('/health'),
    get('/agents'),
    get('/jobs'),
  ])

  const agentList = agents.ok && Array.isArray(agents.data?.agents) ? agents.data.agents : []
  const jobList = jobs.ok && Array.isArray(jobs.data?.jobs) ? jobs.data.jobs : []

  return NextResponse.json({
    connected: Boolean(gateway && token) && health.ok,
    upstreamConfigured: Boolean(gateway && token),
    health: health.ok ? health.data : null,
    agents: agentList,
    jobs: jobList,
    error: health.error || agents.error || jobs.error || null,
    fetchedAt: new Date().toISOString(),
  })
}

export async function POST(req: Request) {
  let body: Record<string, unknown>
  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }

  const action = body.action

  if (demo) {
    if (action === 'queue') {
      const hostname = typeof body.hostname === 'string' ? body.hostname.trim() : ''
      const cmd = typeof body.cmd === 'string' ? body.cmd.trim() : ''
      if (!hostname || !cmd) {
        return NextResponse.json({ ok: false, error: 'hostname and cmd are required' }, { status: 400 })
      }

      const job: Job = {
        id: demoJobs.length + 1,
        hostname,
        cmd,
        status: 'queued',
        created_at: new Date().toISOString(),
        completed_at: null,
        result: { mode: 'demo', message: 'No Linux execution occurred.' },
      }
      demoJobs = [...demoJobs, job].slice(-100)
      return NextResponse.json({ ok: true, data: job, demo: true })
    }

    if (action === 'tag') {
      return NextResponse.json({ ok: true, data: { mode: 'demo', message: 'Tag accepted in demo mode.' }, demo: true })
    }

    if (action === 'pine') {
      return NextResponse.json({ ok: true, data: { mode: 'demo', message: 'Pine request accepted in demo mode.' }, demo: true })
    }

    return NextResponse.json({ ok: false, error: 'unsupported action' }, { status: 400 })
  }

  if (!gateway || !token) {
    return NextResponse.json(
      { ok: false, error: 'AEGIS gateway is not configured. Set AEGIS_GATEWAY_URL and AEGIS_GATEWAY_TOKEN.' },
      { status: 503 },
    )
  }

  if (action === 'queue') {
    const hostname = typeof body.hostname === 'string' ? body.hostname.trim() : ''
    const cmd = typeof body.cmd === 'string' ? body.cmd.trim() : ''
    if (!hostname || !cmd) {
      return NextResponse.json({ ok: false, error: 'hostname and cmd are required' }, { status: 400 })
    }
    if (hostname.length > 255 || cmd.length > 4000) {
      return NextResponse.json({ ok: false, error: 'input exceeds allowed length' }, { status: 400 })
    }

    const result = await request('/queue', {
      method: 'POST',
      body: JSON.stringify({ hostname, cmd }),
    })
    return NextResponse.json(result, { status: result.ok ? 200 : 502 })
  }

  if (action === 'tag') {
    const agentId = Number(body.agent_id)
    const tags = Array.isArray(body.tags)
      ? body.tags
          .filter((tag): tag is string => typeof tag === 'string')
          .map(tag => tag.trim())
          .filter(Boolean)
      : []

    if (!Number.isInteger(agentId) || agentId < 1 || tags.length === 0 || tags.length > 20) {
      return NextResponse.json({ ok: false, error: 'valid agent_id and tags are required' }, { status: 400 })
    }

    const result = await request(`/agents/${agentId}/tag`, {
      method: 'POST',
      body: JSON.stringify({ tags }),
    })
    return NextResponse.json(result, { status: result.ok ? 200 : 502 })
  }

  if (action === 'pine') {
    const agentId = Number(body.agent_id)
    const script = typeof body.script === 'string' ? body.script : ''
    const symbol = typeof body.symbol === 'string' ? body.symbol.trim() : ''

    if (!Number.isInteger(agentId) || agentId < 1 || !script.trim() || !symbol) {
      return NextResponse.json({ ok: false, error: 'agent_id, script and symbol are required' }, { status: 400 })
    }
    if (script.length > 20000 || symbol.length > 100) {
      return NextResponse.json({ ok: false, error: 'input exceeds allowed length' }, { status: 400 })
    }

    const result = await request(`/agents/${agentId}/pine`, {
      method: 'POST',
      body: JSON.stringify({
        script,
        symbol,
        provider: typeof body.provider === 'string' ? body.provider : undefined,
        timeframe: typeof body.timeframe === 'string' ? body.timeframe : undefined,
        limit: Number.isInteger(body.limit) ? body.limit : undefined,
      }),
    })
    return NextResponse.json(result, { status: result.ok ? 200 : 502 })
  }

  return NextResponse.json({ ok: false, error: 'unsupported action' }, { status: 400 })
}
