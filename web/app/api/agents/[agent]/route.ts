import { NextResponse } from 'next/server'
import { getAgentSite } from '../../../../lib/agent-sites'

export const dynamic = 'force-dynamic'

type Params = { params: Promise<{ agent: string }> }

async function readJson(url: URL) {
  try {
    const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(10000) })
    const data = await response.json().catch(() => ({}))
    return { ok: response.ok, data }
  } catch (error) {
    return { ok: false, data: { ok: false, error: error instanceof Error ? error.message : 'source unavailable' } }
  }
}

function sourceUrl(request: Request, path: string) {
  return new URL(path, request.url)
}

export async function GET(request: Request, { params }: Params) {
  const { agent } = await params
  const site = getAgentSite(agent)
  if (!site) return NextResponse.json({ ok: false, error: 'agent site not found' }, { status: 404 })

  const control = await readJson(sourceUrl(request, '/api/control-plane'))
  const allNodes = Array.isArray(control.data?.agents) ? control.data.agents : []
  const nodes = allNodes.filter((node: { tags?: unknown }) => Array.isArray(node.tags) && node.tags.includes(site.tag))
  const hostnames = new Set(nodes.map((node: { hostname?: string }) => node.hostname).filter(Boolean))
  const allJobs = Array.isArray(control.data?.jobs) ? control.data.jobs : []
  const jobs = allJobs.filter((job: { hostname?: string }) => hostnames.has(job.hostname))

  const sources: Record<string, unknown> = {}
  if (site.dataSources.includes('knowledge')) {
    const knowledge = await readJson(sourceUrl(request, '/api/knowledge?departments=1'))
    const departments = Array.isArray(knowledge.data?.departments)
      ? knowledge.data.departments.filter((department: { id?: string }) => site.departmentIds.includes(department.id || ''))
      : []
    sources.knowledge = { departments, research: knowledge.data?.research || null, error: knowledge.ok ? null : knowledge.data?.error }
  }
  if (site.dataSources.includes('prospects')) {
    const prospects = await readJson(sourceUrl(request, '/api/prospects?businesses=1&limit=8'))
    sources.prospects = { businesses: Array.isArray(prospects.data?.businesses) ? prospects.data.businesses.slice(0, 8) : [], error: prospects.ok ? null : prospects.data?.error }
  }
  if (site.dataSources.includes('previews')) {
    const previews = await readJson(sourceUrl(request, '/api/previews'))
    sources.previews = { items: Array.isArray(previews.data?.previews) ? previews.data.previews : [], error: previews.ok ? null : previews.data?.error }
  }

  return NextResponse.json({
    ok: control.ok,
    site: { ...site, tests: site.tests.map(test => ({ id: test.id, label: test.label, detail: test.detail })) },
    connected: Boolean(control.data?.connected),
    nodes,
    jobs,
    sources,
    fetchedAt: new Date().toISOString(),
    error: control.ok ? null : control.data?.error || 'control plane unavailable',
  })
}

export async function POST(request: Request, { params }: Params) {
  const { agent } = await params
  const site = getAgentSite(agent)
  if (!site) return NextResponse.json({ ok: false, error: 'agent site not found' }, { status: 404 })
  let body: { test_id?: unknown }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ ok: false, error: 'invalid JSON body' }, { status: 400 })
  }
  const test = site.tests.find(item => item.id === body.test_id)
  if (!test) return NextResponse.json({ ok: false, error: 'test is not registered for this agent' }, { status: 400 })

  const control = await readJson(sourceUrl(request, '/api/control-plane'))
  const nodes = Array.isArray(control.data?.agents) ? control.data.agents.filter((node: { tags?: unknown; alive?: boolean }) => Array.isArray(node.tags) && node.tags.includes(site.tag) && node.alive) : []
  const node = nodes[0]
  if (!node?.hostname) return NextResponse.json({ ok: false, error: `no live ${site.label.toLowerCase()} node is assigned` }, { status: 409 })

  const response = await fetch(sourceUrl(request, '/api/control-plane'), {
    method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'queue', hostname: node.hostname, cmd: test.command }),
  })
  const data = await response.json().catch(() => ({}))
  return NextResponse.json({ ...data, site: site.key, test: test.id, hostname: node.hostname }, { status: response.ok ? 200 : response.status })
}
