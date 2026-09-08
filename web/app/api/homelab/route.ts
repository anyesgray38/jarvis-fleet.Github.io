import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

const orchestrator = process.env.AEGIS_ORCHESTRATOR_URL?.replace(/\/$/, '')
const modelRuntime = (process.env.AEGIS_MODEL_RUNTIME_URL || 'http://127.0.0.1:8891').replace(/\/$/, '')

async function probe(url: string, timeout = 2500) {
  try {
    const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(timeout) })
    const data = await response.json().catch(() => ({}))
    return { online: response.ok, data: response.ok ? data : null, error: response.ok ? null : `HTTP ${response.status}` }
  } catch (error) {
    return { online: false, data: null, error: error instanceof Error ? error.message : 'unreachable' }
  }
}

export async function GET() {
  const [runtime, health, agents, jobs] = await Promise.all([
    probe(`${modelRuntime}/health`),
    orchestrator ? probe(`${orchestrator}/health`) : Promise.resolve({ online: false, data: null, error: 'AEGIS_ORCHESTRATOR_URL is not configured' }),
    orchestrator ? probe(`${orchestrator}/agents`) : Promise.resolve({ online: false, data: null, error: 'orchestrator unavailable' }),
    orchestrator ? probe(`${orchestrator}/jobs`) : Promise.resolve({ online: false, data: null, error: 'orchestrator unavailable' }),
  ])

  const agentList = Array.isArray(agents.data?.agents) ? agents.data.agents : []
  const jobList = Array.isArray(jobs.data?.jobs) ? jobs.data.jobs : []
  const liveAgents = agentList.filter((agent: { alive?: boolean }) => agent.alive).length
  const activeJobs = jobList.filter((job: { status?: string }) => ['running', 'queued'].includes(job.status || '')).length
  const connected = Boolean(orchestrator) && health.online

  return NextResponse.json({
    ok: true,
    timestamp: new Date().toISOString(),
    overall: connected && runtime.online ? 'healthy' : connected || runtime.online ? 'degraded' : 'offline',
    services: {
      control_center: { status: 'online' },
      orchestrator: { status: health.online ? 'online' : 'offline', error: health.error },
      model_runtime: { status: runtime.online ? 'online' : 'offline', error: runtime.error, data: runtime.data },
      fleet: { status: agents.online ? 'online' : 'offline', live: liveAgents, total: agentList.length, error: agents.error },
      jobs: { status: jobs.online ? 'online' : 'offline', active: activeJobs, total: jobList.length, error: jobs.error },
    },
  })
}
