import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

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
type Recommendation = {
  id: string
  title: string
  owner: string
  priority: 'HIGH' | 'MEDIUM'
  reason: string
}
type AuditReport = {
  run_id: string
  started_at: string
  completed_at: string
  status: 'PASS' | 'DEGRADED' | 'FAIL'
  summary: { passed: number; failed: number; warnings: number; checks: number }
  checks: AuditCheck[]
  recommendations: Recommendation[]
}

const gateway = (process.env.AEGIS_GATEWAY_URL || 'http://127.0.0.1:8877').replace(/\/$/, '')
const gatewayToken = process.env.AEGIS_GATEWAY_TOKEN
const knowledge = (process.env.AEGIS_KNOWLEDGE_URL || 'http://127.0.0.1:8892').replace(/\/$/, '')
const knowledgeToken = process.env.AEGIS_KNOWLEDGE_TOKEN
const orchestrator = (process.env.AEGIS_ORCHESTRATOR_URL || 'http://127.0.0.1:8888').replace(/\/$/, '')
const modelRuntime = (process.env.AEGIS_MODEL_RUNTIME_URL || 'http://127.0.0.1:8891').replace(/\/$/, '')
const web = 'http://127.0.0.1:3000'

let latest: AuditReport | null = null

async function probe(
  id: string,
  name: string,
  owner: string,
  url: string,
  options: RequestInit = {},
  evaluate: (response: Response, data: any) => { status: CheckStatus; detail: string; evidence: string } = (response, data) => ({
    status: response.ok && data?.ok !== false ? 'PASS' : 'FAIL',
    detail: response.ok ? 'Endpoint responded successfully.' : `Endpoint returned HTTP ${response.status}.`,
    evidence: JSON.stringify(data).slice(0, 240),
  }),
): Promise<AuditCheck> {
  const started = Date.now()
  try {
    const response = await fetch(url, { ...options, cache: 'no-store', signal: AbortSignal.timeout(10000) })
    const data = await response.json().catch(() => ({}))
    const result = evaluate(response, data)
    return { id, name, owner, ...result, duration_ms: Date.now() - started }
  } catch (error) {
    return { id, name, owner, status: 'FAIL', detail: error instanceof Error ? error.message : 'Probe failed.', evidence: 'No response received.', duration_ms: Date.now() - started }
  }
}

function auth(token: string | undefined): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function runAudit(): Promise<AuditReport> {
  const started = new Date()
  const checks = await Promise.all([
    probe('gateway-health', 'Authenticated gateway health', 'Sentinel', `${gateway}/health`, { headers: auth(gatewayToken) }),
    probe('orchestrator-health', 'Orchestrator health', 'Sentinel', `${orchestrator}/health`),
    probe('model-runtime', 'Model runtime readiness', 'Forge', `${modelRuntime}/health`, {}, (response, data) => ({
      status: response.ok && data?.ready !== false ? 'PASS' : 'FAIL',
      detail: response.ok ? (data?.ready === false ? 'Runtime responded but is not ready.' : 'Runtime is responding and ready.') : `Runtime returned HTTP ${response.status}.`,
      evidence: JSON.stringify({ ok: data?.ok, ready: data?.ready, providers: data?.providers }).slice(0, 240),
    })),
    probe('knowledge-health', 'Knowledge runtime and MCP configuration', 'Scribe', `${knowledge}/health`, { headers: auth(knowledgeToken) }, (response, data) => ({
      status: response.ok && data?.providers?.wikipedia && data?.providers?.firecrawl ? 'PASS' : 'FAIL',
      detail: response.ok && data?.providers?.firecrawl ? 'Knowledge runtime reports Wiki and Firecrawl MCP configured.' : 'Knowledge runtime or inbound provider is unavailable.',
      evidence: JSON.stringify({ providers: data?.providers, firecrawl_mcp: data?.firecrawl_mcp }).slice(0, 240),
    })),
    probe('firecrawl-admission', 'Firecrawl MCP live admission', 'Atlas', `${knowledge}/health?deep=1`, { headers: auth(knowledgeToken) }, (response, data) => ({
      status: response.ok && data?.firecrawl_mcp?.admitted ? 'PASS' : 'FAIL',
      detail: data?.firecrawl_mcp?.admitted ? 'Aegis admitted the configured Firecrawl MCP server during this audit.' : data?.firecrawl_mcp?.error || 'Firecrawl MCP was not admitted during this audit.',
      evidence: JSON.stringify(data?.firecrawl_mcp || {}).slice(0, 240),
    })),
    probe('knowledge-freshness', 'Inbound knowledge freshness', 'Scribe', `${knowledge}/snapshot`, { headers: auth(knowledgeToken) }, (response, data) => {
      const latestSource = Array.isArray(data?.sources) ? data.sources[0] : null
      const ageHours = latestSource?.updated_at ? (Date.now() - new Date(latestSource.updated_at).getTime()) / 3600000 : Infinity
      const fresh = Number.isFinite(ageHours) && ageHours <= 48
      return { status: response.ok && fresh ? 'PASS' : 'WARN', detail: latestSource ? `Latest packet is ${Math.max(0, Math.round(ageHours * 10) / 10)} hour(s) old.` : 'No inbound packet is available to evaluate.', evidence: JSON.stringify({ latest: latestSource?.title, updated_at: latestSource?.updated_at, packets_ready: data?.metrics?.packets_ready }).slice(0, 240) }
    }),
    probe('gateway-auth-boundary', 'Gateway rejects unauthenticated requests', 'Sentinel', `${gateway}/health`, {}, (response, data) => ({
      status: response.status === 401 ? 'PASS' : 'FAIL',
      detail: response.status === 401 ? 'Unauthenticated gateway access was rejected.' : `Expected HTTP 401, received HTTP ${response.status}.`,
      evidence: JSON.stringify(data).slice(0, 240),
    })),
    probe('knowledge-auth-boundary', 'Knowledge runtime rejects unauthenticated requests', 'Sentinel', `${knowledge}/snapshot`, {}, (response, data) => ({
      status: response.status === 401 ? 'PASS' : 'FAIL',
      detail: response.status === 401 ? 'Unauthenticated knowledge access was rejected.' : `Expected HTTP 401, received HTTP ${response.status}.`,
      evidence: JSON.stringify(data).slice(0, 240),
    })),
    probe('dashboard-health', 'Dashboard responds on the private interface', 'Forge', web, {}, (response) => ({
      status: response.ok ? 'PASS' : 'FAIL',
      detail: response.ok ? 'Dashboard returned a healthy HTTP response.' : `Dashboard returned HTTP ${response.status}.`,
      evidence: `HTTP ${response.status}`,
    })),
  ])

  const recommendations: Recommendation[] = checks.filter(check => check.status !== 'PASS').map(check => ({
    id: `fix-${check.id}`,
    title: check.name,
    owner: check.owner,
    priority: check.id.includes('auth') || check.id.includes('gateway') ? 'HIGH' : 'MEDIUM',
    reason: check.detail,
  }))
  const passed = checks.filter(check => check.status === 'PASS').length
  const failed = checks.filter(check => check.status === 'FAIL').length
  const warnings = checks.filter(check => check.status === 'WARN').length
  const report: AuditReport = {
    run_id: `audit-${started.getTime()}`,
    started_at: started.toISOString(),
    completed_at: new Date().toISOString(),
    status: failed ? 'FAIL' : warnings ? 'DEGRADED' : 'PASS',
    summary: { passed, failed, warnings, checks: checks.length },
    checks,
    recommendations,
  }
  latest = report
  return report
}

export async function GET() {
  return NextResponse.json({ ok: true, report: latest })
}

export async function POST() {
  const report = await runAudit()
  return NextResponse.json({ ok: report.status !== 'FAIL', report }, { status: report.status === 'FAIL' ? 503 : 200 })
}
