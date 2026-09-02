import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const upstream = process.env.AEGIS_ORCHESTRATOR_URL?.replace(/\/$/, '')

async function get(path: string) {
  if (!upstream) return { ok: false, error: 'AEGIS_ORCHESTRATOR_URL is not configured' }
  try {
    const response = await fetch(`${upstream}${path}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(4000),
    })
    if (!response.ok) return { ok: false, error: `upstream returned ${response.status}` }
    return { ok: true, data: await response.json() }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'upstream unavailable' }
  }
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
